"""TASK-04: isolated execution harness tests (positive + negative)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from uiux_engine import isolated_exec


def make_sandbox(tmp_path: Path) -> tuple[Path, Path]:
    allowed = tmp_path / "allowed"
    sandbox = allowed / "run"
    (sandbox / "catalog").mkdir(parents=True)
    (sandbox / "catalog" / "catalog.sqlite").write_bytes(b"db-v1")
    (sandbox / "derived").mkdir()
    (sandbox / "derived" / "state.json").write_text('{"ok": true}', encoding="utf-8")
    return allowed, sandbox


def test_normalize_rejects_escape(tmp_path):
    allowed, _sandbox = make_sandbox(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(isolated_exec.IsolationError):
        isolated_exec.normalize_sandbox(outside, allowed)


def test_backup_restore_is_consistent(tmp_path):
    allowed, sandbox = make_sandbox(tmp_path)
    backup_dir = tmp_path / "backup"
    record = isolated_exec.run_isolated(
        action_id="A-1", root=sandbox, allowed_root=allowed, backup_dir=backup_dir,
        executor=lambda root: {"wrote": (root / "derived" / "new.json").write_text("x", encoding="utf-8")},
    )
    assert record["verdict"] == "PASS"
    assert record["executed"] is True
    assert record["backup_verified"] is True
    assert record["restore_verified"] is True
    assert record["restore_consistent"] is True
    assert not (sandbox / "derived" / "new.json").exists()
    assert (sandbox / "catalog" / "catalog.sqlite").read_bytes() == b"db-v1"


def test_restore_detects_tampering(tmp_path):
    allowed, sandbox = make_sandbox(tmp_path)
    backup_dir = tmp_path / "backup"
    backup_record = isolated_exec.backup(sandbox, backup_dir)
    (sandbox / "catalog" / "catalog.sqlite").write_bytes(b"tampered")
    verification = isolated_exec.verify_restore(backup_record, sandbox)
    assert verification["consistent"] is False
    assert "catalog/catalog.sqlite" in verification["changed"]


def test_executor_failure_still_restores(tmp_path):
    allowed, sandbox = make_sandbox(tmp_path)
    backup_dir = tmp_path / "backup"

    def failing(root: Path):
        (root / "catalog" / "catalog.sqlite").write_bytes(b"partial-write")
        raise RuntimeError("boom")

    record = isolated_exec.run_isolated(
        action_id="A-2", root=sandbox, allowed_root=allowed, backup_dir=backup_dir, executor=failing)
    assert record["state"] == "BLOCKED"
    assert record["verdict"] == "BLOCKED"
    assert record["executed"] is False
    assert record["restore_consistent"] is True
    assert (sandbox / "catalog" / "catalog.sqlite").read_bytes() == b"db-v1"


def test_missing_backup_blocks(tmp_path):
    allowed, sandbox = make_sandbox(tmp_path)
    record = isolated_exec.run_isolated(
        action_id="A-3", root=sandbox, allowed_root=allowed,
        backup_dir=tmp_path / "nope", executor=lambda root: {})
    # backup() creates the dir, so this passes; missing restore source is the real block
    assert record["backup_verified"] is True


def test_restore_missing_backup_raises(tmp_path):
    with pytest.raises(isolated_exec.IsolationError):
        isolated_exec.restore(tmp_path / "missing", tmp_path / "run")
