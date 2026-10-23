"""Run the V1.3.3 contract test suite and emit machine-checkable evidence.

Usage:
    python scripts/run_contract_tests.py

Outputs:
    evidence/T0.1/contract-test-evidence.json
    evidence/T0.1/contract-test-stdout.txt
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "evidence" / "T0.1"
RUNTIME = REPO_ROOT / "runtime"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def collect_inputs() -> dict[str, str]:
    inputs: dict[str, str] = {}
    patterns = [
        "contracts/*.json",
        "contracts/**/*.json",
        "runtime/uiux_engine/*.py",
        "tests/*.py",
        "tests/unit/*.py",
        "tests/integration/*.py",
        "tests/fixtures/_build_fixtures.py",
        "tests/fixtures/contracts/**/*.json",
        "tests/fixtures/scenarios/**/*.json",
        "scripts/run_contract_tests.py",
        "scripts/setup_skill.py",
        "scripts/uninstall_skill.py",
        "scripts/build_task_registry.py",
        "skills/**/*.md",
        "skills/**/*.py",
        "SPEC_V1.3.3.md",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "docs/*.md",
        "docs/audits/*.md",
        "plan/*.json",
        "requirements*.txt",
    ]
    for pattern in patterns:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file():
                inputs[str(path.relative_to(REPO_ROOT)).replace("\\", "/")] = sha256_file(path)
    return inputs


def parse_junit(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    suites = root.findall("testsuite") or [root]
    cases: list[dict] = []
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    for suite in suites:
        totals["tests"] += int(suite.get("tests", 0))
        totals["failures"] += int(suite.get("failures", 0))
        totals["errors"] += int(suite.get("errors", 0))
        totals["skipped"] += int(suite.get("skipped", 0))
        totals["time"] += float(suite.get("time", 0.0))
        for case in suite.findall("testcase"):
            status = "PASS"
            if case.find("failure") is not None:
                status = "FAIL"
            elif case.find("error") is not None:
                status = "ERROR"
            elif case.find("skipped") is not None:
                status = "SKIP"
            cases.append(
                {
                    "name": case.get("classname", "") + "::" + case.get("name", ""),
                    "time_s": float(case.get("time", 0.0)),
                    "status": status,
                }
            )
    return {"totals": totals, "cases": cases}


def versions() -> dict[str, str]:
    import importlib.metadata

    import pytest

    return {
        "python": sys.version.split()[0],
        "jsonschema": importlib.metadata.version("jsonschema"),
        "pytest": pytest.__version__,
    }


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    junit_path = EVIDENCE_DIR / "junit.xml"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, "-m", "pytest", "tests", "-q", f"--junitxml={junit_path}"]
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    duration = round(time.time() - started, 3)
    stdout_path = EVIDENCE_DIR / "contract-test-stdout.txt"
    stdout_path.write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr, encoding="utf-8")

    parsed = parse_junit(junit_path) if junit_path.is_file() else {"totals": {}, "cases": []}
    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T0.1-CONTRACT-TESTS",
        "kind": "test_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "baseline_tag": git("describe", "--tags", "--abbrev=0", "HEAD~1") or "v1.3.2-baseline",
        },
        "command": command,
        "cwd": str(REPO_ROOT),
        "exit_code": proc.returncode,
        "duration_s": duration,
        "environment": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "python_executable": sys.executable,
        },
        "tool_versions": versions(),
        "summary": parsed["totals"],
        "failed_cases": [case for case in parsed["cases"] if case["status"] != "PASS"],
        "test_cases": parsed["cases"],
        "acceptance_mapping": {
            "C-02 launcher/suite-link": ["test_install_doctor_launch_and_uninstall"],
            "C-03 manifest hash mismatch": ["test_launch_rejects_manifest_hash_mismatch"],
            "C-04 valid/invalid samples": ["tests/unit/test_schemas.py"],
            "C-05 mixed enums rejected": ["test_mixed_warning_and_gate_state_is_rejected"],
            "C-06 unresolved WARN cannot complete": ["test_warn_without_disposition_blocks_complete"],
            "C-07 G6 cannot be an input gate": ["test_g6_cannot_be_supplied_as_input_gate", "test_top_level_g6_is_rejected"],
            "C-08 audit/redesign gate completeness": ["test_audit_without_runtime_environment_is_partial_not_complete"],
            "C-09 weakest-layer aggregation": ["test_mock_only_coverage_cannot_claim_native_target"],
            "C-10 expired/missing evidence blocked": ["test_expired_evidence_cannot_support_pass"],
            "C-11 L4 required review": ["test_required_l4_review_missing_blocks_complete", "test_production_code_l4_selftest_reviewer_is_rejected"],
            "C-12 non-git/caller_managed policy": ["test_caller_managed_must_match_policy"],
            "C-13 shadow detection": ["test_shadow_detection_reports_project_skill"],
            "C-14 write roots/permissions": ["test_semantic_violations_are_rejected"],
            "C-15 chinese/space path": ["test_project_scope_with_chinese_and_space_path"],
        },
        "input_sha256": collect_inputs(),
        "stdout_sha256": sha256_file(stdout_path),
        "limitations": [
            "This evidence covers contract, gate logic and local install tests only.",
            "It does not prove DSH host discovery, native GUI probes or independent human review.",
            "Tests run against committed fixtures generated by _build_fixtures.py.",
        ],
    }
    evidence_path = EVIDENCE_DIR / "contract-test-evidence.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "summary": parsed["totals"],
                "evidence": str(evidence_path.relative_to(REPO_ROOT)),
                "input_files": len(evidence["input_sha256"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
