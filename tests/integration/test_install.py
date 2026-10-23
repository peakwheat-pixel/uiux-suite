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
UNINSTALL = REPO_ROOT / "scripts" / "uninstall_skill.py"


def run_script(script: Path, *args: str, agents_home: Path, dsh_home: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DSH_AGENTS_HOME"] = str(agents_home)
    env["DSH_HOME"] = str(dsh_home or (agents_home.parent / ".dsh"))
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    for name in ("runtime", "contracts", "skills"):
        shutil.copytree(REPO_ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__"))
    return source


def install(source: Path, agents_home: Path, version: str = "1.3.3") -> subprocess.CompletedProcess:
    return run_script(SETUP, "install", "--scope", "user", "--source", str(source), "--version", version, agents_home=agents_home)


def test_install_doctor_launch_and_uninstall(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    proc = install(source, agents)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True and payload["activated"] is True

    suite_root = agents / "uiux-suite" / "versions" / "1.3.3"
    assert (suite_root / "RELEASE_MANIFEST.json").is_file()
    link = json.loads((agents / "skills" / "uiux" / "suite-link.json").read_text(encoding="utf-8"))
    assert link["active_version"] == "1.3.3"
    assert link["path_kind"] == "relative_to_skill_root"
    record = agents / "uiux-suite" / "state" / "install-1.3.3.json"
    assert record.is_file()

    doctor = run_script(SETUP, "doctor", "--scope", "user", agents_home=agents)
    assert doctor.returncode in (0, 11), doctor.stdout + doctor.stderr
    doctor_payload = json.loads(doctor.stdout)
    assert doctor_payload["overall_status"] in ("READY", "UNVERIFIED", "MISSING")
    assert doctor_payload["host_capability"]["entries"], "doctor must list discovered skills"

    launch = subprocess.run(
        [sys.executable, str(agents / "skills" / "uiux" / "scripts" / "launch.py"), "enums"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr
    assert json.loads(launch.stdout)["schema_version"] == "1.3.3"

    project_artifact = tmp_path / "project" / ".uiux" / "evidence"
    project_artifact.mkdir(parents=True)
    uninstall = run_script(UNINSTALL, "--scope", "user", "--version", "1.3.3", agents_home=agents)
    assert uninstall.returncode == 0, uninstall.stdout + uninstall.stderr
    assert not (agents / "skills" / "uiux").exists()
    assert not suite_root.exists()
    assert project_artifact.exists(), "uninstall must not touch user artifacts"


def test_launch_works_after_source_tree_is_deleted(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents).returncode == 0
    shutil.rmtree(source)
    launch = subprocess.run(
        [sys.executable, str(agents / "skills" / "uiux" / "scripts" / "launch.py"), "enums"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr
    doctor = run_script(SETUP, "doctor", "--scope", "user", agents_home=agents)
    assert doctor.returncode in (0, 11)


def test_unknown_existing_skill_is_not_overwritten(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    user_skill = agents / "skills" / "uiux"
    user_skill.mkdir(parents=True)
    sentinel = user_skill / "SKILL.md"
    sentinel.write_text("user-owned-content", encoding="utf-8")
    proc = install(source, agents)
    assert proc.returncode == 10
    payload = json.loads(proc.stdout)
    assert payload["code"] == "SKILL_EXISTS"
    assert sentinel.read_text(encoding="utf-8") == "user-owned-content"
    assert not (agents / "uiux-suite" / "versions" / "1.3.3").exists()


def test_version_coexistence_and_uninstall_old(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents, "1.3.3").returncode == 0
    assert install(source, agents, "1.3.2").returncode == 0
    assert (agents / "uiux-suite" / "versions" / "1.3.2").is_dir()
    assert (agents / "uiux-suite" / "versions" / "1.3.3").is_dir()
    link = json.loads((agents / "skills" / "uiux" / "suite-link.json").read_text(encoding="utf-8"))
    assert link["active_version"] == "1.3.3", "older install must not downgrade the active entry"

    uninstall = run_script(UNINSTALL, "--scope", "user", "--version", "1.3.2", agents_home=agents)
    assert uninstall.returncode == 0
    assert not (agents / "uiux-suite" / "versions" / "1.3.2").exists()
    assert (agents / "uiux-suite" / "versions" / "1.3.3").is_dir()
    launch = subprocess.run(
        [sys.executable, str(agents / "skills" / "uiux" / "scripts" / "launch.py"), "enums"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr


def test_shadow_detection_reports_project_skill(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents).returncode == 0
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    project_skill = project / ".agents" / "skills" / "uiux"
    project_skill.mkdir(parents=True)
    (project_skill / "SKILL.md").write_text("---\nname: uiux\ndescription: project copy\n---\n", encoding="utf-8")

    doctor = run_script(SETUP, "doctor", "--scope", "user", "--project", str(project), agents_home=agents)
    assert doctor.returncode in (0, 11), doctor.stdout + doctor.stderr
    payload = json.loads(doctor.stdout)
    uiux_entries = [entry for entry in payload["host_capability"]["entries"] if entry["name"] == "uiux"]
    assert len(uiux_entries) >= 2
    assert any(entry["shadowed_by"] for entry in uiux_entries), f"expected shadowing: {uiux_entries}"


def test_project_scope_with_chinese_and_space_path(tmp_path: Path):
    source = make_source(tmp_path)
    project = tmp_path / "测试 项目"
    project.mkdir()
    proc = run_script(
        SETUP, "install", "--scope", "project", "--project", str(project), "--source", str(source), agents_home=tmp_path / "unused"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    agents = project / ".agents"
    assert (agents / "skills" / "uiux" / "suite-link.json").is_file()
    launch = subprocess.run(
        [sys.executable, str(agents / "skills" / "uiux-verify" / "scripts" / "launch.py"), "enums"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr
    doctor = run_script(
        SETUP,
        "doctor",
        "--scope",
        "project",
        "--project",
        str(project),
        agents_home=agents,
    )
    assert doctor.returncode in (0, 11), doctor.stdout + doctor.stderr


def _launch(agents: Path, skill: str = "uiux") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(agents / "skills" / skill / "scripts" / "launch.py"), "enums"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_launch_rejects_manifest_hash_mismatch(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents).returncode == 0
    target = agents / "uiux-suite" / "versions" / "1.3.3" / "contracts" / "enums.v1.3.3.json"
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")
    proc = _launch(agents)
    assert proc.returncode == 6, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["code"] == "MANIFEST_MISMATCH"
    doctor = run_script(SETUP, "doctor", "--scope", "user", agents_home=agents)
    assert doctor.returncode == 11, doctor.stdout + doctor.stderr
    payload = json.loads(doctor.stdout)
    assert any("MANIFEST_MISMATCH" in problem for problem in payload["problems"])


def test_launch_reports_missing_link_and_version_mismatch(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents).returncode == 0
    link_path = agents / "skills" / "uiux" / "suite-link.json"
    link = json.loads(link_path.read_text(encoding="utf-8"))
    link["active_version"] = "9.9.9"
    link_path.write_text(json.dumps(link), encoding="utf-8")
    proc = _launch(agents)
    assert proc.returncode == 6
    assert json.loads(proc.stdout)["code"] == "VERSION_MISMATCH"

    link_path.unlink()
    proc = _launch(agents)
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["code"] == "LINK_MISSING"


def test_upgrade_and_rollback_switch_active_version(tmp_path: Path):
    source = make_source(tmp_path)
    agents = tmp_path / "agents"
    assert install(source, agents, "1.3.3").returncode == 0

    upgrade = run_script(SETUP, "upgrade", "--scope", "user", "--source", str(source), "--version", "1.3.4", agents_home=agents)
    assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr
    link = json.loads((agents / "skills" / "uiux" / "suite-link.json").read_text(encoding="utf-8"))
    assert link["active_version"] == "1.3.4"
    assert _launch(agents).returncode == 0

    again = run_script(SETUP, "upgrade", "--scope", "user", "--source", str(source), "--version", "1.3.4", agents_home=agents)
    assert again.returncode == 10
    assert json.loads(again.stdout)["code"] == "UPGRADE_NOT_NEWER"

    rollback = run_script(SETUP, "rollback", "--scope", "user", "--version", "1.3.3", agents_home=agents)
    assert rollback.returncode == 0, rollback.stdout + rollback.stderr
    link = json.loads((agents / "skills" / "uiux" / "suite-link.json").read_text(encoding="utf-8"))
    assert link["active_version"] == "1.3.3"
    assert _launch(agents).returncode == 0
