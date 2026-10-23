from __future__ import annotations

import pytest

from conftest import load_fixture
from uiux_engine import policy

REQUEST = load_fixture("contracts/valid/task-request-redesign.json")


def _facts_overrides(**overrides):
    facts = policy.facts_from_request(REQUEST)
    facts.update(overrides)
    return facts


def test_matrix_is_fully_machine_readable():
    doc = policy.load_mode_gate_policy()
    allowed = {"MANDATORY", "REVIEW_ONLY", "CONDITIONAL", "NOT_APPLICABLE"}
    for mode, spec in doc["modes"].items():
        for gate, cell in spec["gates"].items():
            applicability = cell["applicability"] if isinstance(cell, dict) else cell
            assert applicability in allowed, f"{mode}/{gate} has {applicability}"
            if applicability == "CONDITIONAL":
                assert "when" in cell and isinstance(cell["when"], dict)


EXPECTED = {
    "audit": {"G0": "MANDATORY", "G1": "MANDATORY", "G2": "REVIEW_ONLY", "G3": "REVIEW_ONLY", "G4": "REVIEW_ONLY", "G5": "MANDATORY"},
    "design-only": {"G0": "MANDATORY", "G1": "MANDATORY", "G2": "MANDATORY", "G3": "MANDATORY", "G4": "NOT_APPLICABLE", "G5": "NOT_APPLICABLE"},
    "prototype": {"G0": "MANDATORY", "G1": "MANDATORY", "G2": "MANDATORY", "G3": "MANDATORY", "G4": "MANDATORY", "G5": "MANDATORY"},
    "new-build": {"G0": "MANDATORY", "G1": "NOT_APPLICABLE", "G2": "MANDATORY", "G3": "MANDATORY", "G4": "MANDATORY", "G5": "MANDATORY"},
    "redesign": {"G0": "MANDATORY", "G1": "MANDATORY", "G2": "MANDATORY", "G3": "MANDATORY", "G4": "MANDATORY", "G5": "MANDATORY"},
    "targeted-fix": {"G0": "MANDATORY", "G1": "MANDATORY", "G2": "MANDATORY", "G3": "MANDATORY", "G4": "MANDATORY", "G5": "MANDATORY"},
    "verify": {"G0": "MANDATORY", "G1": "REVIEW_ONLY", "G2": "REVIEW_ONLY", "G3": "REVIEW_ONLY", "G4": "REVIEW_ONLY", "G5": "MANDATORY"},
}


@pytest.mark.parametrize("mode,expected", sorted(EXPECTED.items()))
def test_mode_gate_matrix(mode, expected):
    facts = policy.facts_from_request(REQUEST)
    facts["mode"] = mode
    facts["mode"] = mode
    resolved = policy.resolve_mode_gates(mode, facts)
    assert resolved == expected


def test_conditional_g1_for_design_only_depends_on_existing_ui():
    facts = _facts_overrides(**{"project.has_existing_ui": True})
    assert policy.resolve_applicability("design-only", "G1", facts) == "MANDATORY"
    facts = _facts_overrides(**{"project.has_existing_ui": False})
    assert policy.resolve_applicability("design-only", "G1", facts) == "NOT_APPLICABLE"


def test_g6_is_derived_not_an_input_gate():
    doc = policy.load_mode_gate_policy()
    assert doc["derived_gates"] == ["G6"]
    for spec in doc["modes"].values():
        assert "G6" not in spec["gates"]


def test_runtime_min_level_production_requires_native():
    facts = policy.facts_from_request(REQUEST)
    assert policy.gate_min_level("redesign", "G5", facts) == "NATIVE_APP"
    facts_os = dict(facts)
    facts_os["runtime_targets"] = ["SIMULATED", "NATIVE_APP", "OS_INTEGRATION"]
    assert policy.gate_min_level("redesign", "G5", facts_os) == "OS_INTEGRATION"


def test_independent_review_required_for_verify_and_release_audit():
    assert policy.independent_review_required("verify", REQUEST) is True
    request = load_fixture("contracts/valid/task-request-redesign.json")
    request["evidence_policy"]["profile"] = "release_audit"
    assert policy.independent_review_required("redesign", request) is True
    request["evidence_policy"]["profile"] = "local_private"
    request["review"]["independent_required"] = False
    assert policy.independent_review_required("redesign", request) is False


def test_l4_required_by_mode():
    assert policy.l4_required("redesign") is True
    assert policy.l4_required("design-only") is True
    assert policy.l4_required("audit") is False
    assert policy.l4_required("targeted-fix") is False
