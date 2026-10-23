from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT

from uiux_engine import snapshot


def make_tree(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")
    (root / "src" / "b.py").write_text("print('b')\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("ignored\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_bytes(b"cache")
    return root


def test_dir_digest_is_deterministic_and_ignores_cache(tmp_path: Path):
    root = make_tree(tmp_path / "project")
    first = snapshot.dir_digest(root)
    second = snapshot.dir_digest(root)
    assert first == second
    assert set(first) == {"src/a.py", "src/b.py"}


def test_diff_detects_added_removed_changed(tmp_path: Path):
    root = make_tree(tmp_path / "project")
    before = snapshot.build_snapshot(root)
    (root / "src" / "a.py").write_text("print('changed')\n", encoding="utf-8")
    (root / "src" / "c.py").write_text("print('c')\n", encoding="utf-8")
    (root / "src" / "b.py").unlink()
    after = snapshot.build_snapshot(root)
    diff = snapshot.diff_snapshots(before, after)
    assert diff["added"] == ["src/c.py"]
    assert diff["removed"] == ["src/b.py"]
    assert diff["changed"] == ["src/a.py"]
    assert diff["identical"] is False


def test_backup_tree_copies_and_refuses_existing(tmp_path: Path):
    root = make_tree(tmp_path / "project")
    target = snapshot.backup_tree(root, tmp_path / "backup")
    assert (target / "src" / "a.py").is_file()
    assert not (target / ".git").exists()
    try:
        snapshot.backup_tree(root, target)
    except FileExistsError:
        pass
    else:  # pragma: no cover
        raise AssertionError("backup must not overwrite an existing destination")


def test_cli_snapshot_and_diff(tmp_path: Path):
    root = make_tree(tmp_path / "project")
    out = tmp_path / "snap1.json"
    backup = tmp_path / "backup"
    env = {"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1"}
    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "uiux_engine.cli",
            "snapshot",
            "--root",
            str(root),
            "--out",
            str(out),
            "--backup",
            str(backup),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**__import__("os").environ, **env},
    )
    assert first.returncode == 0, first.stdout + first.stderr
    payload = json.loads(first.stdout)
    assert payload["file_count"] == 2
    assert payload["backup"] == str(backup)
    assert (backup / "src" / "a.py").is_file()
    assert not (backup / ".git").exists()

    (root / "src" / "a.py").write_text("changed\n", encoding="utf-8")
    second = subprocess.run(
        [sys.executable, "-m", "uiux_engine.cli", "snapshot", "--root", str(root), "--out", str(tmp_path / "snap2.json")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**__import__("os").environ, **env},
    )
    assert second.returncode == 0, second.stdout + second.stderr
    diff = subprocess.run(
        [
            sys.executable,
            "-m",
            "uiux_engine.cli",
            "snapshot",
            "--diff",
            str(out),
            str(tmp_path / "snap2.json"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**__import__("os").environ, **env},
    )
    assert diff.returncode == 11
    payload = json.loads(diff.stdout)
    assert payload["changed"] == ["src/a.py"]
