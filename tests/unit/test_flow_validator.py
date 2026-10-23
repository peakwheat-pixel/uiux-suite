from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from uiux_engine import flow_validator


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flows"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def gt() -> dict:
    return json.loads((FIXTURES / "gt.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", list(gt()))
def test_ground_truth(name: str):
    report = flow_validator.validate(load(name))
    expected = gt()[name]
    actual_rules = sorted({finding["rule_id"] for finding in report["findings"]})
    assert actual_rules == sorted(expected["expected_rules"])
    assert report["summary"]["fail"] == expected["expected_fail"]
    assert report["schema_valid"] is True


def test_good_flow_is_ok():
    report = flow_validator.validate(load("good.json"))
    assert report["ok"] is True
    assert report["findings"] == []
    assert report["unverified_paths"] == []


def test_irreversible_without_guard_is_fail():
    flows = load("good.json")
    flows["tasks"][0]["destructive_operations"][0]["guard"] = "none"
    report = flow_validator.validate(flows)
    assert report["ok"] is False
    assert any(finding["rule_id"] == "UX-FLOW-002" for finding in report["findings"])


def test_duplicate_task_id_is_rejected():
    flows = load("good.json")
    flows["tasks"].append(copy.deepcopy(flows["tasks"][0]))
    report = flow_validator.validate(flows)
    assert any("duplicate task_id" in finding["message"] for finding in report["findings"])


def test_invalid_schema_returns_single_fail():
    flows = load("good.json")
    flows["view_archetype"] = "not-a-view"
    report = flow_validator.validate(flows)
    assert report["schema_valid"] is False
    assert report["ok"] is False
    assert len(report["findings"]) == 1


def test_missing_capability_evidence_is_unverified_path():
    flows = load("good.json")
    flows["capability_evidence"] = [
        item for item in flows["capability_evidence"] if item["capability"] != "async_load"
    ]
    report = flow_validator.validate(flows)
    assert report["unverified_paths"]
    assert any(item["reason_code"] == "UNVERIFIED_PATH" for item in report["unverified_paths"])


def test_guard_without_evidence_is_fail():
    flows = load("good.json")
    del flows["tasks"][0]["destructive_operations"][0]["evidence_refs"]
    report = flow_validator.validate(flows)
    assert any("without evidence" in finding["message"] for finding in report["findings"])


def test_empty_state_requirement_is_warning():
    flows = load("good.json")
    flows["tasks"][0]["states"] = ["list", "loading", "error", "retry", "draft"]
    report = flow_validator.validate(flows)
    warnings = [finding for finding in report["findings"] if finding["rule_id"] == "UX-FLOW-003"]
    assert warnings and warnings[0]["severity"] == "WARNING"


def test_error_recovery_requirement():
    flows = load("unreachable.json")
    flows["tasks"][0]["entry_point"] = "list"
    flows["tasks"][0]["states"] = ["list", "loading"]
    report = flow_validator.validate(flows)
    assert any(finding["rule_id"] == "UX-FLOW-004" for finding in report["findings"])


def test_rule_ids_exist_in_catalog():
    from uiux_engine import rules

    known = {rule["rule_id"] for rule in rules.load_catalog()["rules"]}
    assert set(flow_validator.FLOW_RULES) <= known


def test_loading_state_requirement_is_warning():
    flows = load("good.json")
    flows["tasks"][0]["states"] = ["list", "empty", "error", "retry", "draft", "saved"]
    report = flow_validator.validate(flows)
    assert any(finding["rule_id"] == "UX-STATE-001" for finding in report["findings"])


def test_cycle_like_repeated_states_do_not_crash():
    flows = load("good.json")
    flows["tasks"][0]["states"] = ["list", "list", "loading", "empty", "error", "retry", "draft"]
    report = flow_validator.validate(flows)
    assert report["schema_valid"] is True
