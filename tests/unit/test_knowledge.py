from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT

from uiux_engine import knowledge


def test_index_schema_valid_and_verifies():
    index = knowledge.load_index()
    report = knowledge.verify(index)
    assert report["ok"], report["problems"]
    assert len(report["verified"]) >= 3
    assert any(item["id"] == "KN-WCAG22" for item in report["skipped"])


def test_index_has_required_kinds():
    index = knowledge.load_index()
    kinds = {entry["kind"] for entry in index["entries"]}
    assert {"rule_catalog", "design_tokens", "guideline", "reference"} <= kinds
    assert all(entry["license"] != "unknown" for entry in index["entries"] if entry.get("path"))


def test_reference_only_entry_has_no_checksum_bundled():
    index = knowledge.load_index()
    reference = next(entry for entry in index["entries"] if entry["kind"] == "reference")
    assert reference["checksum"] is None
    assert "path" not in reference


def test_missing_file_is_reported(tmp_path: Path):
    index = copy.deepcopy(knowledge.load_index())
    index["entries"][0]["path"] = "does/not/exist.json"
    report = knowledge.verify(index, tmp_path)
    assert report["ok"] is False
    assert any("missing file" in problem for problem in report["problems"])


def test_checksum_mismatch_is_reported(tmp_path: Path):
    target = tmp_path / "data.json"
    target.write_text("changed", encoding="utf-8")
    index = copy.deepcopy(knowledge.load_index())
    index["entries"] = [
        {
            "id": "KN-TEST-1",
            "kind": "example",
            "title": "test",
            "source": "self-authored",
            "license": "internal",
            "path": "data.json",
            "checksum": "0" * 64,
        }
    ]
    report = knowledge.verify(index, tmp_path)
    assert report["ok"] is False
    assert any("checksum mismatch" in problem for problem in report["problems"])


def test_bundled_entry_without_checksum_is_rejected(tmp_path: Path):
    target = tmp_path / "data.json"
    target.write_text("x", encoding="utf-8")
    index = copy.deepcopy(knowledge.load_index())
    index["entries"] = [
        {
            "id": "KN-TEST-2",
            "kind": "example",
            "title": "test",
            "source": "self-authored",
            "license": "internal",
            "path": "data.json",
            "checksum": None,
        }
    ]
    report = knowledge.verify(index, tmp_path)
    assert report["ok"] is False
    assert any("no checksum" in problem for problem in report["problems"])


def test_cli_knowledge_verifies():
    env = {"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "uiux_engine.cli", "knowledge"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **env},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
