"""TASK-06: runtime-to-source binding levels and tamper detection."""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from uiux_engine import binding
from uiux_engine.cli import main as cli_main

COPY = Path(r"G:\AI\uiux-workbench-copy")
EXE = COPY / "apps" / "desktop" / "src-tauri" / "target" / "release" / "m2rc1-desktop.exe"


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "apps" / "desktop" / "frontend" / "src").mkdir(parents=True)
    (repo / "apps" / "desktop" / "frontend" / "src" / "main.tsx").write_text("export const a = 1;\n", encoding="utf-8")
    rg = str(COPY / ".git")  # not used; local git init below
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@t.local"],
        ["config", "user.name", "t"],
        ["add", "-A"],
        ["commit", "-q", "-m", "init"],
    ):
        subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)
    return repo


def _make_exe(tmp_path: Path, content: bytes = b"fake-runtime-binary") -> Path:
    exe = tmp_path / "runtime.exe"
    exe.write_bytes(content)
    return exe


def test_source_fingerprint_records_head_dirty_tree(tmp_path):
    repo = _make_repo(tmp_path)
    fp = binding.source_fingerprint(repo)
    assert fp["kind"] == "git_commit"
    assert len(fp["value"]) == 40
    assert fp["dirty"] is False
    assert len(fp["tree_digest"]) == 64
    (repo / "apps" / "desktop" / "frontend" / "src" / "new.tsx").write_text("x", encoding="utf-8")
    assert binding.source_fingerprint(repo)["dirty"] is True


def test_bind_without_manifest_is_artifact_hash(tmp_path):
    repo = _make_repo(tmp_path)
    exe = _make_exe(tmp_path)
    record = binding.bind_runtime(exe, repo)
    assert record["level"] == "artifact_hash"
    assert record["runtime"]["sha256"] == binding.sha256_file(exe)
    assert binding.verify_binding(record, exe, repo) == []


def test_bind_with_manifest_is_build_provenance(tmp_path):
    repo = _make_repo(tmp_path)
    exe = _make_exe(tmp_path)
    exe_hash = binding.sha256_file(exe)
    manifest = tmp_path / "RELEASE_MANIFEST.json"
    manifest.write_text(json.dumps({"files": [{"path": "runtime.exe", "sha256": exe_hash}]}), encoding="utf-8")
    record = binding.bind_runtime(exe, repo, manifest)
    assert record["level"] == "build_provenance"


def test_dirty_source_refuses_build_provenance(tmp_path):
    repo = _make_repo(tmp_path)
    exe = _make_exe(tmp_path)
    exe_hash = binding.sha256_file(exe)
    manifest = tmp_path / "RELEASE_MANIFEST.json"
    manifest.write_text(json.dumps({"files": [{"path": "runtime.exe", "sha256": exe_hash}]}), encoding="utf-8")
    (repo / "apps" / "desktop" / "frontend" / "src" / "dirty.tsx").write_text("x", encoding="utf-8")
    record = binding.bind_runtime(exe, repo, manifest)
    assert record["level"] != "build_provenance"
    assert any("dirty" in check["detail"] for check in record["checks"] if not check["ok"])


def test_verify_detects_runtime_and_source_tamper(tmp_path):
    repo = _make_repo(tmp_path)
    exe = _make_exe(tmp_path)
    record = binding.bind_runtime(exe, repo)
    exe.write_bytes(b"tampered")
    problems = binding.verify_binding(record, exe, repo)
    assert any("RUNTIME_HASH_MISMATCH" in problem for problem in problems)

    exe2 = _make_exe(tmp_path, b"other")
    record2 = binding.bind_runtime(exe2, repo)
    (repo / "apps" / "desktop" / "frontend" / "src" / "main.tsx").write_text("changed", encoding="utf-8")
    problems = binding.verify_binding(record2, exe2, repo)
    assert any("SOURCE_TREE_MISMATCH" in problem for problem in problems)


def test_level_ordering():
    assert binding.level_at_least({"level": "build_provenance"}, "artifact_hash")
    assert not binding.level_at_least({"level": "runtime_marker"}, "artifact_hash")
    assert binding.level_at_least({"level": "artifact_hash"}, "runtime_marker")
    assert not binding.level_at_least({"level": "NONE"}, "runtime_marker")


@pytest.mark.skipif(not EXE.is_file(), reason="New Manga runtime exe not present on this host")
def test_real_workbench_copy_binding():
    record = binding.bind_runtime(EXE, COPY)
    assert record["level"] in ("artifact_hash", "build_provenance")
    assert record["runtime"]["sha256"]
    assert binding.verify_binding(record, EXE, COPY) == []
    assert record["source"]["dirty"] is True  # V1.3.3 audit sandbox state is recorded, not hidden


def test_cli_binding_generate_and_verify(tmp_path):
    repo = _make_repo(tmp_path)
    exe = _make_exe(tmp_path)
    out = tmp_path / "binding.json"
    assert cli_main(["binding", "--exe", str(exe), "--source", str(repo), "--out", str(out)]) == 0
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["level"] == "artifact_hash"
    assert cli_main(["binding", "--verify", str(out), "--exe", str(exe), "--source", str(repo)]) == 0
    exe.write_bytes(b"tampered")
    assert cli_main(["binding", "--verify", str(out), "--exe", str(exe), "--source", str(repo)]) == 10
