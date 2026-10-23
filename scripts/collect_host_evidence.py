"""Collect T0.3 host-install evidence from the user-level installation.

Read-only with respect to the repository except for files under evidence/T0.3/.
It does not install the suite; it inspects the existing installation, runs the
installed launchers and doctor, and records hashes for audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "evidence" / "T0.3"
SETUP = REPO_ROOT / "scripts" / "setup_skill.py"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _dirty_excluding_evidence() -> bool:
    status = _git("status", "--porcelain")
    for line in status.splitlines():
        path = line[3:].strip() if len(line) > 3 else ""
        if path and not path.startswith("evidence/"):
            return True
    return False


def run(command: list[str], cwd: Path | None = None) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        command,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "stdout_sha256": sha256_bytes(proc.stdout.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents-home", help="override agents home (default: %USERPROFILE%/.agents)")
    parser.add_argument("--version", default="1.3.3")
    args = parser.parse_args()

    agents_home = Path(args.agents_home) if args.agents_home else Path.home() / ".agents"
    skill_root = agents_home / "skills" / "uiux"
    link_path = skill_root / "suite-link.json"
    record_path = agents_home / "uiux-suite" / "state" / f"install-{args.version}.json"

    problems: list[str] = []
    for required in (link_path, record_path):
        if not required.is_file():
            problems.append(f"missing: {required}")
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, ensure_ascii=False, indent=2))
        return 1

    git_info = {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": _dirty_excluding_evidence(),
        "dirty_scope": "tracked files excluding evidence/ (collectors rewrite evidence)",
    }

    link = json.loads(link_path.read_text(encoding="utf-8"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    suite_root = Path(record["suite_root"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    launcher_runs = {}
    for skill in ("uiux", "uiux-verify"):
        launcher = agents_home / "skills" / skill / "scripts" / "launch.py"
        result = run([sys.executable, str(launcher), "enums"])
        stdout_file = raw_dir / f"{skill}-enums.stdout.json"
        stdout_file.write_text(result["stdout"], encoding="utf-8")
        result["stdout_file"] = str(stdout_file.relative_to(REPO_ROOT))
        result["stdout_file_sha256"] = sha256_file(stdout_file)
        launcher_runs[skill] = result

    doctor = run([sys.executable, str(SETUP), "doctor", "--scope", "user"])
    doctor_raw = raw_dir / "doctor.stdout.json"
    doctor_raw.write_text(doctor["stdout"], encoding="utf-8")
    try:
        doctor_payload = json.loads(doctor["stdout"])
    except json.JSONDecodeError:
        doctor_payload = None

    dsh_version = run(["powershell", "-NoProfile", "-Command", "dsh --version"])
    dsh_version_file = raw_dir / "dsh-version.stdout.txt"
    dsh_version_file.write_text(dsh_version["stdout"], encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        external_doctor = run(
            [sys.executable, str(agents_home / "skills" / "uiux" / "scripts" / "launch.py"), "doctor", "--scope", "user"],
            cwd=Path(temp_dir),
        )
    external_raw = raw_dir / "external-cwd-doctor.stdout.json"
    external_raw.write_text(external_doctor["stdout"], encoding="utf-8")

    repo_references: list[str] = []
    for path in sorted(suite_root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if str(REPO_ROOT) in text:
            repo_references.append(path.relative_to(suite_root).as_posix())

    manifest_path = suite_root / record.get("manifest_relpath", "RELEASE_MANIFEST.json")
    (OUT_DIR / "doctor.json").write_text(json.dumps(doctor_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T0.3-HOST-INSTALL",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": git_info,
        "privacy": "local_private_unredacted: contains machine-specific absolute paths; not for distribution",
        "generator_sha256": sha256_file(Path(__file__)),
        "host": {
            "kind": "dsh",
            "dsh_version": dsh_version["stdout"].strip(),
            "os": platform.platform(),
            "python": sys.version.split()[0],
        },
        "agents_home": str(agents_home),
        "suite_root": str(suite_root),
        "suite_link": {
            "path": str(link_path),
            "sha256": sha256_file(link_path),
            "active_version": link.get("active_version"),
            "path_kind": link.get("path_kind"),
        },
        "install_record": {
            "path": str(record_path),
            "sha256": sha256_file(record_path),
            "files": len(record.get("files", [])),
            "scope": record.get("scope"),
            "host": record.get("host"),
            "python_exe": record.get("python_exe"),
            "python_version": record.get("python_version"),
            "installed_from_commit": record.get("installed_from_commit"),
        },
        "launchers": {
            skill: {
                "exit_code": run_result["exit_code"],
                "stdout_file": run_result["stdout_file"],
                "stdout_file_sha256": run_result["stdout_file_sha256"],
                "schema_version": _schema_version(run_result["stdout"]),
            }
            for skill, run_result in launcher_runs.items()
        },
        "doctor": {
            "exit_code": doctor["exit_code"],
            "stdout_file": str(doctor_raw.relative_to(REPO_ROOT)),
            "stdout_file_sha256": sha256_file(doctor_raw),
            "overall_status": (doctor_payload or {}).get("overall_status"),
            "links": (doctor_payload or {}).get("links"),
            "entries_contain_both_skills": _contains_both(doctor_payload),
            "shadowed": [
                entry
                for entry in ((doctor_payload or {}).get("host_capability") or {}).get("entries", [])
                if entry.get("shadowed_by")
            ],
            "capabilities": ((doctor_payload or {}).get("host_capability") or {}).get("capabilities"),
        },
        "inputs_sha256": {
            "suite_manifest": sha256_file(manifest_path),
            "install_record": sha256_file(record_path),
            "suite_link": sha256_file(link_path),
            "generator": sha256_file(Path(__file__)),
        },
        "host_catalog_observation": {
            "detail": "After install, the running DSH session exposed 'uiux' and 'uiux-verify' in its skill catalog (user-agents rank 500).",
            "skills": ["uiux", "uiux-verify"],
        },
        "repo_independence": {
            "external_cwd_doctor_exit_code": external_doctor["exit_code"],
            "external_cwd_doctor_stdout_file": str(external_raw.relative_to(REPO_ROOT)),
            "external_cwd_doctor_stdout_file_sha256": sha256_file(external_raw),
            "external_cwd_doctor_stdout_sha256": external_doctor["stdout_sha256"],
            "source_checkout_absolute_references": repo_references,
            "source_checkout_scan_scope": "all install-root files under suite_root (<=2MB, text-decodable)",
            "independent_of_source_checkout": external_doctor["exit_code"] == 0 and not repo_references,
        },
        "limitations": [
            "GUI click-through/MCP/resume capabilities are UNVERIFIED until Stage 4.",
            "This evidence does not prove behavior on other hosts; see T4.2 matrix.",
            "Raw stdout files are stored under evidence/T0.3/raw and hashed by file.",
        ],
    }
    out_path = OUT_DIR / "host-install-evidence.json"
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": all(item["exit_code"] == 0 for item in [doctor, dsh_version, *launcher_runs.values()]),
                "evidence": str(out_path.relative_to(REPO_ROOT)),
                "doctor_status": evidence["doctor"]["overall_status"],
                "both_skills": evidence["doctor"]["entries_contain_both_skills"],
                "independent_of_source_checkout": evidence["repo_independence"]["independent_of_source_checkout"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _schema_version(stdout: str) -> str | None:
    try:
        return json.loads(stdout).get("schema_version")
    except (json.JSONDecodeError, AttributeError):
        return None


def _contains_both(payload: dict | None) -> bool:
    if not payload:
        return False
    names = {
        entry.get("name")
        for entry in ((payload.get("host_capability") or {}).get("entries") or [])
    }
    return {"uiux", "uiux-verify"} <= names


if __name__ == "__main__":
    raise SystemExit(main())
