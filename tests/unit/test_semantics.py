from __future__ import annotations

import copy

import pytest

from conftest import load_fixture
from uiux_engine import validation

REQUEST = load_fixture("contracts/valid/task-request-redesign.json")
AUDIT_REQUEST = load_fixture("contracts/valid/task-request-audit.json")
RESULT = load_fixture("contracts/valid/task-result.json")
GATE_RESULTS = load_fixture("contracts/valid/gate-results.json")


@pytest.mark.parametrize("request_fixture", ["contracts/valid/task-request-redesign.json", "contracts/valid/task-request-audit.json"])
def test_valid_requests_have_no_semantic_errors(request_fixture):
    request = load_fixture(request_fixture)
    assert validation.request_semantic_errors(request) == []


SEMANTIC_CASES = {
    "task-request-readonly-with-writes.json": "READ_ONLY_VIOLATION",
    "task-request-physical-input-no-auth.json": "AUTHORIZATION_MISSING",
    "task-request-missing-native-target.json": "RUNTIME_TARGET_NOT_COVERED",
    "task-request-write-scope-not-subset.json": "WRITE_SCOPE_VIOLATION",
    "task-request-overlap-roots.json": "POLICY_INVALID",
}


@pytest.mark.parametrize("fixture_name,expected_code", sorted(SEMANTIC_CASES.items()))
def test_semantic_violations_are_rejected(fixture_name, expected_code):
    request = load_fixture(f"contracts/semantic-invalid/{fixture_name}")
    codes = [problem["code"] for problem in validation.request_semantic_errors(request)]
    assert expected_code in codes, f"{fixture_name}: got {codes}"


def test_physical_input_requires_authorization_scope():
    request = copy.deepcopy(REQUEST)
    request["execution_policy"]["allow_physical_os_input"] = True
    request["execution_policy"]["os_input_target_allowlist"] = ["demo.exe"]
    request["policy"]["permissions"]["os_input"]["physical"] = True
    request["policy"]["authorization"] = {
        "granted_by": "tester",
        "granted_at": "2026-10-23T12:00:00+00:00",
        "expires_at": None,
        "scopes": ["production_write"],
        "evidence_ref": "EV-AUTH",
    }
    codes = [problem["code"] for problem in validation.request_semantic_errors(request)]
    assert "AUTHORIZATION_MISSING" in codes


def test_caller_managed_must_match_policy():
    request = copy.deepcopy(AUDIT_REQUEST)
    request["caller"]["git_management"] = "caller_managed"
    codes = [problem["code"] for problem in validation.request_semantic_errors(request)]
    assert "POLICY_INVALID" in codes


def test_valid_result_passes_cross_schema_semantics():
    assert validation.result_semantic_errors(RESULT, REQUEST, GATE_RESULTS) == []


def test_result_fingerprint_mismatch_is_rejected():
    tampered = copy.deepcopy(RESULT)
    tampered["source_fingerprint"] = {"kind": "git_commit", "value": "b" * 40}
    codes = [problem["code"] for problem in validation.result_semantic_errors(tampered, REQUEST, GATE_RESULTS)]
    assert "SOURCE_FINGERPRINT_MISMATCH" in codes


def test_complete_with_non_pass_g6_is_rejected():
    tampered = copy.deepcopy(RESULT)
    tampered["derived_g6"]["state"] = "UNVERIFIED"
    codes = [problem["code"] for problem in validation.result_semantic_errors(tampered, REQUEST, GATE_RESULTS)]
    assert "COMPLETE_CONSTRAINT_VIOLATION" in codes


def test_unregistered_reason_code_is_rejected():
    tampered = copy.deepcopy(RESULT)
    tampered["status"] = "PARTIAL"
    tampered["delivery_status"] = "PARTIAL_VERIFIED"
    tampered["blocking_reasons"] = [{"gate": "G5", "code": "MADE_UP_CODE", "detail": "fake"}]
    codes = [problem["code"] for problem in validation.result_semantic_errors(tampered, REQUEST, GATE_RESULTS)]
    assert "RESULT_INVALID" in codes


def test_unverified_path_reason_code_must_be_registered():
    tampered = copy.deepcopy(RESULT)
    tampered["status"] = "PARTIAL"
    tampered["delivery_status"] = "PARTIAL_VERIFIED"
    tampered["derived_g6"]["state"] = "UNVERIFIED"
    tampered["unverified_paths"] = [
        {"task_id": "import", "scenario_id": "native-import", "reason_code": "MADE_UP", "detail": "fake"}
    ]
    codes = [problem["code"] for problem in validation.result_semantic_errors(tampered, REQUEST, GATE_RESULTS)]
    assert "RESULT_INVALID" in codes


def test_gate_reason_codes_must_be_registered():
    tampered = copy.deepcopy(GATE_RESULTS)
    tampered["gates"]["G5"]["reason_codes"] = ["MADE_UP_CODE"]
    codes = [problem["code"] for problem in validation.gate_results_semantic_errors(tampered)]
    assert "GATE_STATE_INVALID" in codes
