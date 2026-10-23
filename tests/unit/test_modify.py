from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uiux_engine import modify


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.tsx").write_text("export const App = () => null;\n", encoding="utf-8")
    (root / "README.md").write_text("# project\n", encoding="utf-8")
    return root


def plan(root: Path, changes: list[dict], scope: list[str] | None = None) -> dict:
    return {
        "schema_version": "1.3.3",
        "plan_id": "PLAN-TEST",
        "task_id": "T3.1",
        "created_at": "2026-10-24T00:00:00+00:00",
        "write_scope": scope or ["src/"],
        "changes": changes,
    }


def test_modify_existing_file(tmp_path: Path):
    root = make_project(tmp_path)
    before = file_sha(root / "src" / "app.tsx")
    data = plan(root, [{"path": "src/app.tsx", "action": "modify", "sha256_before": before, "content": "export const App = 1;\n"}])
    result = modify.apply_plan(data, root)
    assert result["ok"] is True
    assert (root / "src" / "app.tsx").read_text(encoding="utf-8") == "export const App = 1;\n"
    assert Path(result["backup"]).is_dir()


def test_create_and_delete(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(
        root,
        [
            {"path": "src/new.ts", "action": "create", "content": "export {};\n"},
            {"path": "src/app.tsx", "action": "delete", "sha256_before": file_sha(root / "src" / "app.tsx")},
        ],
    )
    result = modify.apply_plan(data, root)
    assert result["ok"] is True
    assert (root / "src" / "new.ts").is_file()
    assert not (root / "src" / "app.tsx").exists()


def test_outside_scope_is_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [{"path": "README.md", "action": "modify", "sha256_before": file_sha(root / "README.md"), "content": "x"}], scope=["src/"])
    result = modify.apply_plan(data, root)
    assert result["ok"] is False
    assert any("outside write scope" in problem for problem in result["problems"])
    assert (root / "README.md").read_text(encoding="utf-8") == "# project\n"


def test_traversal_is_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [{"path": "../escape.txt", "action": "create", "content": "x"}])
    result = modify.apply_plan(data, root)
    assert result["ok"] is False
    assert not (root.parent / "escape.txt").exists()


def test_hash_mismatch_is_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [{"path": "src/app.tsx", "action": "modify", "sha256_before": "0" * 64, "content": "x"}])
    result = modify.apply_plan(data, root)
    assert result["ok"] is False
    assert any("hash mismatch" in problem for problem in result["problems"])


def test_create_existing_is_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [{"path": "src/app.tsx", "action": "create", "content": "x"}])
    result = modify.apply_plan(data, root)
    assert result["ok"] is False


def test_dry_run_does_not_write(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [{"path": "src/new.ts", "action": "create", "content": "export {};\n"}])
    diffs = modify.diff_plan(data, root)
    assert diffs[0]["before"] is None
    assert diffs[0]["after"] == sha("export {};\n")
    assert not (root / "src" / "new.ts").exists()


def test_revert_restores_modified_file(tmp_path: Path):
    root = make_project(tmp_path)
    original = (root / "src" / "app.tsx").read_text(encoding="utf-8")
    data = plan(root, [{"path": "src/app.tsx", "action": "modify", "sha256_before": file_sha(root / "src" / "app.tsx"), "content": "changed\n"}])
    result = modify.apply_plan(data, root)
    assert result["ok"] is True
    revert = modify.revert_plan(data, root, result["backup"])
    assert revert["ok"] is True
    assert (root / "src" / "app.tsx").read_text(encoding="utf-8") == original


def test_revert_removes_created_file(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [{"path": "src/new.ts", "action": "create", "content": "x"}])
    result = modify.apply_plan(data, root)
    assert (root / "src" / "new.ts").is_file()
    modify.revert_plan(data, root, result["backup"])
    assert not (root / "src" / "new.ts").exists()


def test_schema_invalid_plan_is_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    data = plan(root, [])
    result = modify.apply_plan(data, root)
    assert result["ok"] is False
    assert result["problems"]
