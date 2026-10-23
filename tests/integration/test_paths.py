from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

SETUP = REPO_ROOT / "scripts" / "setup_skill.py"


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    for name in ("runtime", "contracts", "skills"):
        shutil.copytree(REPO_ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__"))
    return source


def install(source: Path, agents_home: Path, project: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DSH_AGENTS_HOME"] = str(agents_home)
    env["DSH_HOME"] = str(agents_home.parent / ".dsh")
    env["PYTHONUTF8"] = "1"
    args = [sys.executable, str(SETUP), "--host", "generic", "install", "--source", str(source)]
    if project is None:
        args += ["--scope", "user"]
    else:
        args += ["--scope", "project", "--project", str(project)]
    return subprocess.run(args, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def launch(agents: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(agents / "skills" / "uiux" / "scripts" / "launch.py"), "enums"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows-only junction semantics")
def test_project_install_through_junction(tmp_path: Path):
    source = make_source(tmp_path)
    real = tmp_path / "real-project"
    real.mkdir()
    junction = tmp_path / "junction-project"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(real)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if created.returncode != 0:
        pytest.skip(f"junction unsupported: {created.stdout}{created.stderr}")
    try:
        proc = install(source, tmp_path / "unused", project=junction)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        agents = junction / ".agents"
        assert (agents / "skills" / "uiux" / "suite-link.json").is_file()
        run = launch(agents)
        assert run.returncode == 0, run.stdout + run.stderr
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows-only long path semantics")
def test_project_install_with_long_path(tmp_path: Path):
    source = make_source(tmp_path)
    long_root = tmp_path
    for index in range(6):
        long_root = long_root / ("segment-" + str(index) * 24)
    long_root.mkdir(parents=True)
    assert len(str(long_root)) > 260
    proc = install(source, tmp_path / "unused", project=long_root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    agents = long_root / ".agents"
    run = launch(agents)
    assert run.returncode == 0, run.stdout + run.stderr


def test_custom_rank_300_is_reported(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents).returncode == 0
    custom = tmp_path / "custom-skills"
    (custom / "uiux").mkdir(parents=True)
    (custom / "uiux" / "SKILL.md").write_text("# custom uiux\n", encoding="utf-8")
    env = dict(os.environ)
    env["DSH_AGENTS_HOME"] = str(agents)
    env["DSH_HOME"] = str(tmp_path / ".dsh")
    env["UIUX_CUSTOM_SKILLS_HOME"] = str(custom)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, str(SETUP), "--host", "dsh", "doctor", "--scope", "user"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode in (0, 11), proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    roots = payload["host_capability"]["skill_roots"]
    custom_roots = [root for root in roots if root["source"] == "custom"]
    assert custom_roots and custom_roots[0]["rank"] == 300
    entries = [entry for entry in payload["host_capability"]["entries"] if entry["name"] == "uiux"]
    winner = min(entries, key=lambda entry: entry["rank"])
    assert winner["rank"] == 300
    assert any(entry["rank"] == 500 and entry["shadowed_by"] for entry in entries)

    skill_root = tmp_path / "skills" / "uiux"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# fake\n", encoding="utf-8")
    launcher = REPO_ROOT / "skills" / "uiux" / "scripts" / "launch.py"
    shutil.copy2(launcher, skill_root / "scripts" / "launch.py")
    (skill_root / "suite-link.json").write_text(
        json.dumps(
            {
                "schema_version": "1.3.3",
                "suite_id": "universal-uiux-engineering",
                "active_version": "1.3.3",
                "path_kind": "absolute",
                "suite_root": r"\\127.0.0.1\uiux-missing-share\1.3.3",
                "manifest_relpath": "RELEASE_MANIFEST.json",
                "python_exe": sys.executable,
                "created_by_installer": False,
                "created_at": "2026-10-24T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(skill_root / "scripts" / "launch.py"), "enums"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["code"] == "RELEASE_ROOT_MISSING"
