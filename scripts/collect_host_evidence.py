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

    link = json.loads(link_path.read_text(encoding="utf-8"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    suite_root = Path(record["suite_root"])

    launcher_runs = {}
    for skill in ("uiux", "uiux-verify"):
        launcher = agents_home / "skills" / skill / "scripts" / "launch.py"
        launcher_runs[skill] = run([sys.executable, str(launcher), "enums"])

    doctor = run([sys.executable, str(SETUP), "doctor", "--scope", "user"])
    try:
        doctor_payload = json.loads(doctor["stdout"])
    except json.JSONDecodeError:
        doctor_payload = None

    dsh_version = run(["powershell", "-NoProfile", "-Command", "dsh --version"])

    with tempfile.TemporaryDirectory() as temp_dir:
        external_doctor = run(
            [sys.executable, str(agents_home / "skills" / "uiux" / "scripts" / "launch.py"), "doctor", "--scope", "user"],
            cwd=Path(temp_dir),
        )
    repo_references = sorted(
        {
            str(REPO_ROOT)
            for path in (link_path, record_path)
            if str(REPO_ROOT) in path.read_text(encoding="utf-8")
        }
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "doctor.json").write_text(json.dumps(doctor_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T0.3-HOST-INSTALL",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
        },
        "launchers": {
            skill: {
                "exit_code": run_result["exit_code"],
                "stdout_sha256": run_result["stdout_sha256"],
                "schema_version": _schema_version(run_result["stdout"]),
            }
            for skill, run_result in launcher_runs.items()
        },
        "doctor": {
            "exit_code": doctor["exit_code"],
            "stdout_sha256": doctor["stdout_sha256"],
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
        "host_catalog_observation": {
            "detail": "After install, the running DSH session exposed 'uiux' and 'uiux-verify' in its skill catalog (user-agents rank 500).",
            "skills": ["uiux", "uiux-verify"],
        },
        "repo_independence": {
            "external_cwd_doctor_exit_code": external_doctor["exit_code"],
            "external_cwd_doctor_stdout_sha256": external_doctor["stdout_sha256"],
            "source_checkout_absolute_references": repo_references,
            "independent_of_source_checkout": external_doctor["exit_code"] == 0 and not repo_references,
        },
        "limitations": [
            "GUI click-through/MCP/resume capabilities are UNVERIFIED until Stage 4.",
            "This evidence does not prove behavior on other hosts; see T4.2 matrix.",
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
