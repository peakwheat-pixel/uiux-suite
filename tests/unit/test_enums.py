from __future__ import annotations

import pytest

from uiux_engine import contracts, enums


def test_enum_dictionary_self_check():
    assert enums.self_check() == []


def test_enum_rank_orders():
    assert enums.rank("RuntimeEvidenceLevel", "SIMULATED") < enums.rank("RuntimeEvidenceLevel", "NATIVE_APP")
    assert enums.rank("RuntimeEvidenceLevel", "NATIVE_APP") < enums.rank("RuntimeEvidenceLevel", "OS_INTEGRATION")
    assert enums.rank("ReviewIsolationLevel", "SELFTEST") < enums.rank("ReviewIsolationLevel", "INDEPENDENT_AGENT")


def test_reason_codes_are_unique_and_grouped():
    codes = enums.reason_codes()
    assert len(codes) == len(enums.load_enums()["reason_codes"])
    assert "LAYER_SPOOF_OR_MISSING" in codes
    assert "WARN_REVIEW_MISSING" in codes
    assert "LINK_MISSING" in codes


@pytest.mark.parametrize("schema_name", sorted(contracts.SCHEMA_FILES))
def test_every_schema_enum_belongs_to_one_dictionary_namespace(schema_name):
    namespaces = {name: set(spec["values"]) for name, spec in enums.load_enums()["enums"].items()}
    for path, values in contracts.collect_enum_values(schema_name):
        value_set = set(values)
        matches = [name for name, allowed in namespaces.items() if value_set <= allowed]
        assert matches, f"{schema_name}{path} does not fit any enum namespace: {sorted(value_set)}"


FIELD_NAMESPACES = {
    ("gate-results", "$/properties/mode"): "Mode",
    ("gate-results", "$/$defs/gate_result/properties/state"): "GateState",
    ("gate-results", "$/$defs/gate_result/properties/applicability"): "GateApplicability",
    ("gate-results", "$/$defs/gate_result/properties/required_runtime_level"): "RuntimeEvidenceLevel",
    ("gate-results", "$/$defs/gate_result/properties/observed_runtime_level"): "RuntimeEvidenceLevel",
    ("gate-results", "$/$defs/gate_result/properties/gate_id"): "GateId",
    ("task-result", "$/properties/status"): "RunStatus",
    ("task-result", "$/properties/delivery_status"): "DeliveryStatus",
    ("task-result", "$/properties/independent_review_status"): "IndependentReviewStatus",
    ("task-result", "$/properties/design_review_status"): "DesignReviewStatus",
    ("task-result", "$/properties/runtime_evidence_level"): "RuntimeEvidenceLevel",
    ("task-result", "$/properties/review_isolation_level"): "ReviewIsolationLevel",
    ("design-review", "$/properties/overall_verdict"): "ReviewVerdict",
}


@pytest.mark.parametrize("key,namespace", sorted(FIELD_NAMESPACES.items()))
def test_critical_enum_fields_belong_to_declared_namespace(key, namespace):
    schema_name, path = key
    matches = [values for found_path, values in contracts.collect_enum_values(schema_name) if found_path == path]
    assert matches, f"{schema_name}{path} not found"
    assert set(matches[0]) <= set(enums.values(namespace)), (
        f"{schema_name}{path} must use {namespace}, got {sorted(matches[0])}"
    )


def test_gate_state_does_not_accept_rule_severity_warning():
    assert "WARNING" not in enums.values("GateState")
    assert "WARNING" in enums.values("RuleSeverity")
    assert enums.mapping("rule_severity_to_gate_state")["WARNING"] == "WARN_REVIEW_REQUIRED"


def test_rule_severity_maps_to_gate_state_without_mixing():
    mapping = enums.mapping("rule_severity_to_gate_state")
    assert mapping == {"FAIL": "FAIL", "WARNING": "WARN_REVIEW_REQUIRED", "INFO": "PASS"}
    assert "WARNING" in enums.values("RuleSeverity")
    assert "WARNING" not in enums.values("GateState")


def test_runtime_target_enum_matches_runtime_evidence_levels():
    assert enums.values("RuntimeTarget") == ("SIMULATED", "NATIVE_APP", "OS_INTEGRATION")
    assert set(enums.values("RuntimeTarget")).issubset(set(enums.values("RuntimeEvidenceLevel")))
