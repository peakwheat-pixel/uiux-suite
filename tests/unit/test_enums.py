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
def test_every_schema_enum_value_belongs_to_dictionary(schema_name):
    all_values = set()
    for spec in enums.load_enums()["enums"].values():
        all_values.update(spec["values"])
    for path, values in contracts.collect_enum_values(schema_name):
        unknown = [value for value in values if value not in all_values]
        assert not unknown, f"{schema_name}{path} has values absent from enums.v1.3.3.json: {unknown}"


def test_rule_severity_maps_to_gate_state_without_mixing():
    mapping = enums.mapping("rule_severity_to_gate_state")
    assert mapping == {"FAIL": "FAIL", "WARNING": "WARN_REVIEW_REQUIRED", "INFO": "PASS"}
    assert "WARNING" in enums.values("RuleSeverity")
    assert "WARNING" not in enums.values("GateState")


def test_runtime_target_enum_matches_runtime_evidence_levels():
    assert enums.values("RuntimeTarget") == ("SIMULATED", "NATIVE_APP", "OS_INTEGRATION")
    assert set(enums.values("RuntimeTarget")).issubset(set(enums.values("RuntimeEvidenceLevel")))
