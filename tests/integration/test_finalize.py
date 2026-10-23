from __future__ import annotations

import copy

import pytest

from conftest import load_fixture
from uiux_engine import gates

REQUEST = load_fixture("contracts/valid/task-request-redesign.json")
GATE_RESULTS = load_fixture("contracts/valid/gate-results.json")
COVERAGE = load_fixture("contracts/valid/coverage-matrix.json")
MANIFEST = load_fixture("contracts/valid/evidence-manifest.json")
TOOL_LOGS = load_fixture("scenarios/complete-redesign/tool-logs.json")
DESIGN_REVIEW = load_fixture("contracts/valid/design-review.json")
ATTESTATION = load_fixture("contracts/valid/review-attestation.json")
NOW = "2026-10-23T12:00:00+00:00"


def _evaluate(**overrides):
    params = {
        "request": copy.deepcopy(REQUEST),
        "gate_results": copy.deepcopy(GATE_RESULTS),
        "coverage": copy.deepcopy(COVERAGE),
        "manifest": copy.deepcopy(MANIFEST),
        "tool_logs": copy.deepcopy(TOOL_LOGS),
        "design_review": copy.deepcopy(DESIGN_REVIEW),
        "review_attestation": copy.deepcopy(ATTESTATION),
        "warn_reviews": [],
    }
    params.update(overrides)
    from uiux_engine.evidence import parse_time

    return gates.evaluate_run(now=parse_time(NOW), **params)


def _codes(outcome):
    return {reason["code"] for reason in outcome["blocking_reasons"]}


def test_happy_path_complete_with_independent_review():
    outcome = _evaluate()
    assert outcome["status"] == "COMPLETE"
    assert outcome["delivery_status"] == "INDEPENDENT_VERIFIED"
    assert outcome["independent_review_status"] == "INDEPENDENT_REVIEW_PASS"
    assert outcome["derived_g6"]["state"] == "PASS"
    assert outcome["runtime_evidence_level"] == "NATIVE_APP"
    assert outcome["blocking_reasons"] == []
    assert outcome["unverified_paths"] == []


def test_warn_without_disposition_blocks_complete():
    gate_results = copy.deepcopy(GATE_RESULTS)
    gate_results["gates"]["G5"]["state"] = "WARN_REVIEW_REQUIRED"
    outcome = _evaluate(gate_results=gate_results)
    assert outcome["status"] != "COMPLETE"
    assert "WARN_REVIEW_MISSING" in _codes(outcome)
    assert outcome["derived_g6"]["state"] != "PASS"


def test_warn_with_valid_disposition_can_complete():
    gate_results = copy.deepcopy(GATE_RESULTS)
    gate_results["gates"]["G5"]["state"] = "WARN_REVIEW_REQUIRED"
    review = {
        "finding_id": "F-001",
        "gate": "G5",
        "disposition": "ACCEPTED_RISK",
        "reviewer_source": "isolated_session",
        "reviewer_identity": "reviewer-01",
        "reviewed_head": "a" * 40,
        "evidence_refs": ["EV-G5"],
        "expires_at": "2027-10-23T12:00:00+00:00",
        "rationale": "accepted with telemetry",
    }
    outcome = _evaluate(gate_results=gate_results, warn_reviews=[review])
    assert outcome["status"] == "COMPLETE"
    assert "WARN_REVIEW_MISSING" not in _codes(outcome)


def test_expired_evidence_cannot_support_pass():
    manifest = copy.deepcopy(MANIFEST)
    for item in manifest["items"]:
        if item["id"] == "EV-G5":
            item["expiry_at"] = "2026-01-01T00:00:00+00:00"
    outcome = _evaluate(manifest=manifest)
    assert outcome["status"] != "COMPLETE"
    assert "EVIDENCE_EXPIRED" in _codes(outcome)


def test_layer_spoof_mock_log_claiming_native_is_rejected():
    logs = copy.deepcopy(TOOL_LOGS)
    for log in logs:
        if log["probe_id"] == "P-G5":
            log["execution_level"] = "SIMULATED"
    outcome = _evaluate(tool_logs=logs)
    assert "LAYER_SPOOF_OR_MISSING" in _codes(outcome)
    assert outcome["status"] != "COMPLETE"


def test_mock_only_coverage_cannot_claim_native_target():
    coverage = copy.deepcopy(COVERAGE)
    for record in coverage["records"]:
        record["required_runtime_level"] = "SIMULATED"
        record["observed_runtime_level"] = "SIMULATED"
    outcome = _evaluate(coverage=coverage)
    assert outcome["runtime_evidence_level"] == "SIMULATED"
    assert "RUNTIME_TARGET_NOT_COVERED" in _codes(outcome)
    assert outcome["status"] != "COMPLETE"


def test_redesign_missing_mandatory_g5_cannot_complete():
    gate_results = copy.deepcopy(GATE_RESULTS)
    gate_results["gates"]["G5"].update({"state": "UNVERIFIED", "evidence_refs": [], "probe_ids": []})
    outcome = _evaluate(gate_results=gate_results)
    assert outcome["status"] != "COMPLETE"
    assert outcome["derived_g6"]["state"] != "PASS"


def test_required_l4_review_missing_blocks_complete():
    outcome = _evaluate(design_review=None)
    assert outcome["design_review_status"] == "MISSING"
    assert outcome["status"] != "COMPLETE"
    assert "DESIGN_REVIEW_MISSING" in _codes(outcome)


def test_unverified_review_source_blocks_independent_acceptance():
    attestation = copy.deepcopy(ATTESTATION)
    attestation["review_origin"]["trust_source"] = "user_attested"
    outcome = _evaluate(review_attestation=attestation)
    assert outcome["independent_review_status"] != "INDEPENDENT_REVIEW_PASS"
    assert outcome["status"] != "COMPLETE"
    assert outcome["delivery_status"] != "INDEPENDENT_VERIFIED"


def test_missing_attestation_when_required_is_not_complete():
    outcome = _evaluate(review_attestation=None)
    assert outcome["independent_review_status"] == "UNVERIFIED"
    assert outcome["status"] != "COMPLETE"


def test_reviewed_head_mismatch_is_rejected():
    attestation = copy.deepcopy(ATTESTATION)
    attestation["reviewed_head"] = "b" * 40
    outcome = _evaluate(review_attestation=attestation)
    assert "REVIEWED_HEAD_MISMATCH" in _codes(outcome)
    assert outcome["independent_review_status"] != "INDEPENDENT_REVIEW_PASS"


def test_blocked_mandatory_gate_yields_blocked_status():
    gate_results = copy.deepcopy(GATE_RESULTS)
    gate_results["gates"]["G5"].update({"state": "BLOCKED", "evidence_refs": [], "probe_ids": []})
    outcome = _evaluate(gate_results=gate_results)
    assert outcome["status"] == "BLOCKED"


def test_audit_without_runtime_environment_is_partial_not_complete():
    from conftest import load_fixture

    audit_request = load_fixture("contracts/valid/task-request-audit.json")
    audit_gates = copy.deepcopy(GATE_RESULTS)
    audit_gates["mode"] = "audit"
    for gate in ("G2", "G3", "G4"):
        audit_gates["gates"][gate].update(
            {"applicability": "REVIEW_ONLY", "state": "UNVERIFIED", "evidence_refs": [], "probe_ids": []}
        )
    audit_gates["gates"]["G5"].update(
        {"state": "UNVERIFIED", "observed_runtime_level": "NONE", "evidence_refs": [], "probe_ids": []}
    )
    outcome = _evaluate(request=audit_request, gate_results=audit_gates, design_review=None, review_attestation=None)
    assert outcome["status"] == "PARTIAL"
    assert outcome["derived_g6"]["state"] != "PASS"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda o: o.update({"runtime_evidence_level": "SIMULATED"}),
    ],
)
def test_outcome_shape_is_stable(mutation):
    outcome = _evaluate()
    sample = copy.deepcopy(outcome)
    mutation(sample)
    assert sample["runtime_evidence_level"] == "SIMULATED"
    assert outcome["status"] == "COMPLETE"
