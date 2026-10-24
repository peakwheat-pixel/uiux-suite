from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import FIXTURES, REPO_ROOT
from uiux_engine import contracts

RUNTIME = REPO_ROOT / "runtime"
SCENARIO = FIXTURES / "scenarios" / "complete-redesign"


def run_cli(*args: str, expect: int | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "uiux_engine.cli", *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if expect is not None:
        assert proc.returncode == expect, f"exit={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    return proc


def test_cli_validates_valid_request():
    proc = run_cli(
        "validate",
        "--schema",
        "task-request",
        "--instance",
        str(FIXTURES / "contracts/valid/task-request-redesign.json"),
        expect=0,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True


def test_cli_rejects_invalid_request():
    proc = run_cli(
        "validate",
        "--schema",
        "task-request",
        "--instance",
        str(FIXTURES / "contracts/invalid/task-request-bad-mode.json"),
        expect=10,
    )
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert any("audit-v2" in error for error in payload["errors"])
    assert payload["errors"], "invalid request must produce schema errors"


def test_cli_finalize_complete_happy_path(tmp_path: Path):
    out = tmp_path / "result.json"
    proc = run_cli(
        "finalize",
        "--request",
        str(SCENARIO / "request.json"),
        "--gate-results",
        str(SCENARIO / "gate-results.json"),
        "--coverage",
        str(SCENARIO / "coverage.json"),
        "--evidence-manifest",
        str(SCENARIO / "evidence-manifest.json"),
        "--tool-logs",
        str(SCENARIO / "tool-logs.json"),
        "--design-review",
        str(SCENARIO / "design-review.json"),
        "--review-attestation",
        str(SCENARIO / "review-attestation.json"),
        "--now",
        "2026-10-23T12:00:00+00:00",
        "--repair-cycles",
        "1",
        "--out",
        str(out),
        expect=0,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "COMPLETE"
    assert payload["g6"] == "PASS"
    assert payload["delivery_status"] == "INDEPENDENT_VERIFIED"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert contracts.validation_errors("task-result", data) == []
    assert data["derived_g6"]["state"] == "PASS"
    assert data["repair_cycles"] == 1


def test_cli_missing_l4_review_is_partial(tmp_path: Path):
    proc = run_cli(
        "finalize",
        "--request",
        str(SCENARIO / "request.json"),
        "--gate-results",
        str(SCENARIO / "gate-results.json"),
        "--coverage",
        str(SCENARIO / "coverage.json"),
        "--evidence-manifest",
        str(SCENARIO / "evidence-manifest.json"),
        "--tool-logs",
        str(SCENARIO / "tool-logs.json"),
        "--review-attestation",
        str(SCENARIO / "review-attestation.json"),
        "--now",
        "2026-10-23T12:00:00+00:00",
        expect=11,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "PARTIAL"
    assert any(reason["code"] == "DESIGN_REVIEW_MISSING" for reason in payload["blocking_reasons"])


def test_cli_rejects_g6_as_input_gate(tmp_path: Path):
    gate_results = json.loads((SCENARIO / "gate-results.json").read_text(encoding="utf-8"))
    gate_results["gates"]["G6"] = dict(gate_results["gates"]["G0"])
    tampered = tmp_path / "gate-results.json"
    tampered.write_text(json.dumps(gate_results), encoding="utf-8")
    proc = run_cli(
        "finalize",
        "--request",
        str(SCENARIO / "request.json"),
        "--gate-results",
        str(tampered),
        "--coverage",
        str(SCENARIO / "coverage.json"),
        "--evidence-manifest",
        str(SCENARIO / "evidence-manifest.json"),
        "--tool-logs",
        str(SCENARIO / "tool-logs.json"),
        "--design-review",
        str(SCENARIO / "design-review.json"),
        "--review-attestation",
        str(SCENARIO / "review-attestation.json"),
        expect=10,
    )
    payload = json.loads(proc.stdout)
    assert any("G6" in error for error in payload["errors"])


def test_cli_policy_matrix_design_only():
    proc = run_cli("policy", "--mode", "design-only", expect=0)
    payload = json.loads(proc.stdout)
    assert payload["gates"]["G1"] == "NOT_APPLICABLE"  # conditional on project.has_existing_ui
    assert payload["gates"]["G4"] == "NOT_APPLICABLE"
    assert payload["derived_gates"] == ["G6"]


def test_cli_enums_prints_dictionary():
    proc = run_cli("enums", expect=0)
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "1.3.4"
    assert "GateState" in payload["enums"]
    assert "ReasonCode" not in payload["enums"]  # reason codes live in their own section


def test_cli_unknown_schema_is_usage_error():
    run_cli("validate", "--schema", "gate-results", "--instance", str(SCENARIO / "gate-results.json"), expect=0)
    proc = run_cli("validate", "--schema", "bogus", "--instance", str(SCENARIO / "gate-results.json"), expect=2)
    assert proc.returncode == 2


def _finalize(scenario, extra: list[str], expect: int):
    return run_cli(
        "finalize",
        "--request",
        str(scenario / "request.json"),
        "--gate-results",
        str(scenario / "gate-results.json"),
        "--coverage",
        str(scenario / "coverage.json"),
        "--evidence-manifest",
        str(scenario / "evidence-manifest.json"),
        "--tool-logs",
        str(scenario / "tool-logs.json"),
        "--design-review",
        str(scenario / "design-review.json"),
        "--review-attestation",
        str(scenario / "review-attestation.json"),
        "--now",
        "2026-10-23T12:00:00+00:00",
        *extra,
        expect=expect,
    )


def test_cli_rejects_invalid_now_timestamp():
    proc = run_cli(
        "finalize",
        "--request",
        str(SCENARIO / "request.json"),
        "--gate-results",
        str(SCENARIO / "gate-results.json"),
        "--coverage",
        str(SCENARIO / "coverage.json"),
        "--evidence-manifest",
        str(SCENARIO / "evidence-manifest.json"),
        "--now",
        "not-a-timestamp",
        expect=2,
    )
    assert "invalid --now" in proc.stdout


def test_cli_rejects_invalid_warn_review_file(tmp_path: Path):
    warn_file = tmp_path / "warn-reviews.json"
    warn_file.write_text(
        json.dumps([{"finding_id": "F-1", "gate": "G5", "disposition": "FIXED"}]),
        encoding="utf-8",
    )
    proc = _finalize(SCENARIO, ["--warn-reviews", str(warn_file)], expect=10)
    payload = json.loads(proc.stdout)
    assert any("warn_reviews" in error for error in payload["errors"])


def test_cli_rejects_request_digest_mismatch(tmp_path: Path):
    gate_results = json.loads((SCENARIO / "gate-results.json").read_text(encoding="utf-8"))
    gate_results["request_digest"] = "0" * 64
    tampered = tmp_path / "gate-results.json"
    tampered.write_text(json.dumps(gate_results), encoding="utf-8")
    proc = run_cli(
        "finalize",
        "--request",
        str(SCENARIO / "request.json"),
        "--gate-results",
        str(tampered),
        "--coverage",
        str(SCENARIO / "coverage.json"),
        "--evidence-manifest",
        str(SCENARIO / "evidence-manifest.json"),
        "--tool-logs",
        str(SCENARIO / "tool-logs.json"),
        "--design-review",
        str(SCENARIO / "design-review.json"),
        "--review-attestation",
        str(SCENARIO / "review-attestation.json"),
        expect=10,
    )
    assert "REQUEST_DIGEST_MISMATCH" in proc.stdout


def test_cli_rejects_repair_cycles_out_of_range():
    proc = run_cli(
        "finalize",
        "--request",
        str(SCENARIO / "request.json"),
        "--gate-results",
        str(SCENARIO / "gate-results.json"),
        "--coverage",
        str(SCENARIO / "coverage.json"),
        "--evidence-manifest",
        str(SCENARIO / "evidence-manifest.json"),
        "--repair-cycles",
        "3",
        expect=2,
    )
    assert "--repair-cycles" in proc.stdout
