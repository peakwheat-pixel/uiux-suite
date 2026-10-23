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
