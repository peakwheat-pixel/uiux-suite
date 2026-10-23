"""T1.6 negative-attack suite: every forged/partial PASS must be rejected."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

SCENARIO = REPO_ROOT / "tests" / "fixtures" / "scenarios" / "complete-redesign"
NOW = "2026-10-23T12:00:00+00:00"


def load(name: str) -> dict:
    return json.loads((SCENARIO / name).read_text(encoding="utf-8"))


def run_finalize(tmp_path: Path, **overrides) -> subprocess.CompletedProcess:
    payload = {
        "request": load("request.json"),
        "gate-results": load("gate-results.json"),
        "coverage": load("coverage.json"),
        "evidence-manifest": load("evidence-manifest.json"),
        "tool-logs": load("tool-logs.json"),
        "design-review": load("design-review.json"),
        "review-attestation": load("review-attestation.json"),
    }
    payload.update(overrides)
    paths: dict[str, str] = {}
    for key, value in payload.items():
        if value is None:
            continue
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        paths[key] = str(path)
    command = [
        sys.executable,
        "-m",
        "uiux_engine.cli",
        "finalize",
        "--request",
        paths["request"],
        "--gate-results",
        paths["gate-results"],
        "--coverage",
        paths["coverage"],
        "--evidence-manifest",
        paths["evidence-manifest"],
        "--tool-logs",
        paths["tool-logs"],
        "--design-review",
        paths["design-review"],
        "--now",
        NOW,
    ]
    if "review-attestation" in paths:
        command += ["--review-attestation", paths["review-attestation"]]
    if "warn-reviews" in paths:
        command += ["--warn-reviews", paths["warn-reviews"]]
    env = {"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**__import__("os").environ, **env},
    )


def codes(payload: dict) -> set[str]:
    return {reason["code"] for reason in payload.get("blocking_reasons", [])}


def test_attack_fake_all_pass_without_evidence_is_rejected(tmp_path: Path):
    manifest = load("evidence-manifest.json")
    manifest["items"] = [item for item in manifest["items"] if item["id"] != "EV-G5"]
    proc = run_finalize(tmp_path, **{"evidence-manifest": manifest})
    assert proc.returncode == 11, proc.stdout + proc.stderr
    assert {"MISSING_EVIDENCE", "PROBE_ID_MISSING"} & codes(json.loads(proc.stdout))


def test_attack_deleted_evidence_blocks(tmp_path: Path):
    manifest = load("evidence-manifest.json")
    for item in manifest["items"]:
        if item["id"] == "EV-G1":
            item["status"] = "SOURCE_EVIDENCE_UNAVAILABLE"
    proc = run_finalize(tmp_path, **{"evidence-manifest": manifest})
    assert proc.returncode == 11
    assert "EVIDENCE_SOURCE_UNAVAILABLE" in codes(json.loads(proc.stdout))


def test_attack_mock_tool_log_claiming_native_is_rejected(tmp_path: Path):
    logs = load("tool-logs.json")
    for log in logs:
        if log["probe_id"] == "P-G5":
            log["execution_level"] = "SIMULATED"
    manifest = load("evidence-manifest.json")
    for item in manifest["items"]:
        if item["id"] == "EV-G5":
            item["provenance"]["execution_level"] = "NATIVE_APP"
    gate_results = load("gate-results.json")
    gate_results["gates"]["G5"]["evidence_refs"][0]["evidence_level"] = "NATIVE_APP"
    proc = run_finalize(tmp_path, **{"tool-logs": logs, "gate-results": gate_results, "evidence-manifest": manifest})
    assert proc.returncode == 11
    assert "LAYER_SPOOF_OR_MISSING" in codes(json.loads(proc.stdout))


def test_attack_coverage_claiming_native_with_mock_provenance_is_rejected(tmp_path: Path):
    coverage = load("coverage.json")
    for record in coverage["records"]:
        record["required_runtime_level"] = "NATIVE_APP"
        record["observed_runtime_level"] = "NATIVE_APP"
        record["probe_id"] = "P-G5"
    manifest = load("evidence-manifest.json")
    for item in manifest["items"]:
        if item["id"] == "EV-G5":
            item["provenance"]["execution_level"] = "SIMULATED"
    logs = load("tool-logs.json")
    for log in logs:
        if log["probe_id"] == "P-G5":
            log["execution_level"] = "SIMULATED"
    proc = run_finalize(tmp_path, **{"coverage": coverage, "evidence-manifest": manifest, "tool-logs": logs})
    assert proc.returncode == 11
    assert "LAYER_SPOOF_OR_MISSING" in codes(json.loads(proc.stdout))


def test_attack_nonzero_tool_exit_is_rejected(tmp_path: Path):
    logs = load("tool-logs.json")
    for log in logs:
        if log["probe_id"] == "P-G5":
            log["exit_code"] = 1
    proc = run_finalize(tmp_path, **{"tool-logs": logs})
    assert proc.returncode == 11
    assert "TOOL_EXIT_NONZERO" in codes(json.loads(proc.stdout))


def test_attack_warn_without_review_is_rejected(tmp_path: Path):
    gate_results = load("gate-results.json")
    gate_results["gates"]["G5"]["state"] = "WARN_REVIEW_REQUIRED"
    proc = run_finalize(tmp_path, **{"gate-results": gate_results})
    assert proc.returncode == 11
    assert "WARN_REVIEW_MISSING" in codes(json.loads(proc.stdout))


def test_attack_warn_review_bound_to_old_head_is_rejected(tmp_path: Path):
    gate_results = load("gate-results.json")
    gate_results["gates"]["G5"]["state"] = "WARN_REVIEW_REQUIRED"
    review = {
        "finding_id": "F-ATTACK",
        "gate": "G5",
        "disposition": "FIXED",
        "reviewer_source": "isolated_session",
        "reviewer_identity": "attacker",
        "reviewed_head": "0" * 40,
        "evidence_refs": ["EV-G5"],
        "expires_at": "2027-10-23T12:00:00+00:00",
        "rationale": "fabricated",
    }
    proc = run_finalize(tmp_path, **{"gate-results": gate_results, "warn-reviews": [review]})
    assert proc.returncode == 11
    assert "REVIEWED_HEAD_MISMATCH" in codes(json.loads(proc.stdout))


def test_attack_request_digest_tamper_is_rejected(tmp_path: Path):
    gate_results = load("gate-results.json")
    gate_results["request_digest"] = "0" * 64
    proc = run_finalize(tmp_path, **{"gate-results": gate_results})
    assert proc.returncode == 10
    assert "REQUEST_DIGEST_MISMATCH" in proc.stdout


def test_attack_top_level_g6_is_rejected_at_schema(tmp_path: Path):
    gate_results = load("gate-results.json")
    gate_results["g6"] = {"state": "PASS", "checks": [], "computed_at": NOW}
    proc = run_finalize(tmp_path, **{"gate-results": gate_results})
    assert proc.returncode == 10


def test_attack_self_declared_independent_attestation_is_rejected(tmp_path: Path):
    attestation = load("review-attestation.json")
    attestation["isolation_level"] = "ISOLATED_SESSION"
    attestation["review_origin"]["trust_source"] = "user_attested"
    proc = run_finalize(tmp_path, **{"review-attestation": attestation})
    assert proc.returncode == 11
    payload = json.loads(proc.stdout)
    assert payload["independent_review_status"] == "INDEPENDENCE_UNVERIFIED"


def test_attack_expired_evidence_is_rejected(tmp_path: Path):
    manifest = load("evidence-manifest.json")
    for item in manifest["items"]:
        item["expiry_at"] = "2026-01-01T00:00:00+00:00"
    proc = run_finalize(tmp_path, **{"evidence-manifest": manifest})
    assert proc.returncode == 11
    assert "EVIDENCE_EXPIRED" in codes(json.loads(proc.stdout))
