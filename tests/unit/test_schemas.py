from __future__ import annotations

import pytest

from conftest import load_fixture, FIXTURES
from uiux_engine import contracts

VALID_CASES = {
    "contracts/valid/task-request-redesign.json": "task-request",
    "contracts/valid/task-request-audit.json": "task-request",
    "contracts/valid/policy.json": "policy",
    "contracts/valid/gate-results.json": "gate-results",
    "contracts/valid/coverage-matrix.json": "coverage-matrix",
    "contracts/valid/evidence-manifest.json": "evidence-manifest",
    "contracts/valid/tool-log.json": "tool-log",
    "contracts/valid/design-review.json": "design-review",
    "contracts/valid/review-attestation.json": "review-attestation",
    "contracts/valid/task-result.json": "task-result",
    "contracts/valid/suite-link.json": "suite-link",
    "contracts/valid/release-manifest.json": "release-manifest",
    "contracts/valid/flows.json": "flows",
    "contracts/valid/host-capability.json": "host-capability",
}

INVALID_CASES = {
    "contracts/invalid/task-request-bad-mode.json": "task-request",
    "contracts/invalid/task-request-absolute-scope.json": "task-request",
    "contracts/invalid/gate-results-warning-token.json": "gate-results",
    "contracts/invalid/gate-results-with-g6.json": "gate-results",
    "contracts/invalid/gate-results-top-level-g6.json": "gate-results",
    "contracts/invalid/task-result-complete-with-blockers.json": "task-result",
    "contracts/invalid/task-result-independent-no-attestation.json": "task-result",
    "contracts/invalid/evidence-available-no-hash.json": "evidence-manifest",
    "contracts/invalid/evidence-redacted-no-hash.json": "evidence-manifest",
    "contracts/invalid/review-attestation-independent-user-attested.json": "review-attestation",
    "contracts/invalid/design-review-nine-dim.json": "design-review",
    "contracts/invalid/suite-link-relative-absolute.json": "suite-link",
    "contracts/invalid/release-manifest-uppercase-hash.json": "release-manifest",
    "contracts/invalid/tool-log-missing-probe.json": "tool-log",
    "contracts/invalid/flows-bad-archetype.json": "flows",
}


@pytest.mark.parametrize("fixture_name,schema_name", sorted(VALID_CASES.items()))
def test_valid_fixtures_validate(fixture_name, schema_name):
    errors = contracts.validation_errors(schema_name, load_fixture(fixture_name))
    assert errors == [], f"{fixture_name}: {errors}"


@pytest.mark.parametrize("fixture_name,schema_name", sorted(INVALID_CASES.items()))
def test_invalid_fixtures_are_rejected(fixture_name, schema_name):
    errors = contracts.validation_errors(schema_name, load_fixture(fixture_name))
    assert errors, f"{fixture_name} unexpectedly validated against {schema_name}"


def test_g6_cannot_be_supplied_as_input_gate():
    data = load_fixture("contracts/invalid/gate-results-with-g6.json")
    errors = contracts.validation_errors("gate-results", data)
    assert any("G6" in error for error in errors)


def test_top_level_g6_is_rejected():
    data = load_fixture("contracts/invalid/gate-results-top-level-g6.json")
    errors = contracts.validation_errors("gate-results", data)
    assert errors, "top-level g6 must be rejected"


def test_mixed_warning_and_gate_state_is_rejected():
    data = load_fixture("contracts/invalid/gate-results-warning-token.json")
    errors = contracts.validation_errors("gate-results", data)
    assert any("WARNING" in error for error in errors)


def test_malformed_datetime_is_rejected():
    data = load_fixture("contracts/valid/gate-results.json")
    data["created_at"] = "not-a-timestamp"
    errors = contracts.validation_errors("gate-results", data)
    assert errors, "date-time format must be enforced"


def test_gate_results_require_request_digest():
    data = load_fixture("contracts/valid/gate-results.json")
    data.pop("request_digest")
    errors = contracts.validation_errors("gate-results", data)
    assert any("request_digest" in error for error in errors)


def test_every_valid_fixture_file_is_covered():
    on_disk = {
        f"contracts/valid/{path.name}" for path in (FIXTURES / "contracts" / "valid").glob("*.json")
    }
    assert on_disk == set(VALID_CASES), f"uncovered valid fixtures: {on_disk ^ set(VALID_CASES)}"
