"""Run the T1.6 negative-attack suite and emit machine-checkable evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "evidence" / "T1.6"
TEST_FILE = REPO_ROOT / "tests" / "integration" / "test_attacks.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    junit = OUT_DIR / "attack-junit.xml"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "runtime")
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-m", "pytest", str(TEST_FILE), "-q", f"--junitxml={junit}"]
    started = time.time()
    proc = subprocess.run(command, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, encoding="utf-8")
    stdout_path = OUT_DIR / "attack-stdout.txt"
    stdout_path.write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr, encoding="utf-8")

    cases: list[dict] = []
    if junit.is_file():
        root = ET.parse(junit).getroot()
        suite = root.find("testsuite")
        if suite is None:
            suite = root
        for case in suite.findall("testcase"):
            status = "PASS"
            if case.find("failure") is not None:
                status = "FAIL"
            elif case.find("error") is not None:
                status = "ERROR"
            elif case.find("skipped") is not None:
                status = "SKIP"
            cases.append({"name": case.get("name"), "status": status, "time_s": float(case.get("time", 0.0))})

    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T1.6-ATTACK-SUITE",
        "kind": "test_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8"
            ).stdout.strip(),
        },
        "command": command,
        "exit_code": proc.returncode,
        "duration_s": round(time.time() - started, 3),
        "cases": cases,
        "summary": {
            "tests": len(cases),
            "passed": sum(case["status"] == "PASS" for case in cases),
            "failed": sum(case["status"] in ("FAIL", "ERROR") for case in cases),
        },
        "inputs_sha256": {
            "test_attacks.py": sha256_file(TEST_FILE),
            "scenario_request": sha256_file(REPO_ROOT / "tests/fixtures/scenarios/complete-redesign/request.json"),
            "scenario_gate_results": sha256_file(REPO_ROOT / "tests/fixtures/scenarios/complete-redesign/gate-results.json"),
            "stdout": sha256_file(stdout_path),
        },
    }
    out = OUT_DIR / "attack-evidence.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": proc.returncode == 0, "exit_code": proc.returncode, "summary": evidence["summary"]}, ensure_ascii=False))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
