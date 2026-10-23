from __future__ import annotations

import copy
import json
from pathlib import Path

from uiux_engine import prototype

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "prototype"


def load(name: str = "prototype.json") -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_valid_prototype_is_checked():
    report = prototype.check(load(), FIXTURES)
    assert report["overall_status"] == "UNVERIFIED"  # keyboard/contrast are honestly unverified
    assert report["errors"] == []
    statuses = {item["check_id"]: item["status"] for item in report["checks"]}
    assert statuses["states-subset"] == "PASS"
    assert statuses["anchors-known"] == "PASS"
    assert statuses["html-testids"] == "PASS"


def test_all_verified_prototype_is_ok():
    data = load()
    data["accessibility"] = {"keyboard": "VERIFIED", "labels": "VERIFIED", "contrast": "VERIFIED"}
    data["checks"] = []
    report = prototype.check(data, FIXTURES)
    assert report["ok"] is True
    assert report["overall_status"] == "PASS"


def test_unknown_state_fails():
    data = load()
    data["states"].append("ghost")
    report = prototype.check(data, FIXTURES)
    assert report["overall_status"] == "FAIL"
    assert any(item["check_id"] == "states-subset" and item["status"] == "FAIL" for item in report["checks"])


def test_unknown_anchor_fails():
    data = load()
    data["anchors"].append({"semantic_id": "orders.ghost", "testid": "ghost", "selector": None})
    report = prototype.check(data, FIXTURES)
    assert any(item["check_id"] == "anchors-known" and item["status"] == "FAIL" for item in report["checks"])


def test_missing_flows_fails():
    data = load()
    data["flows_ref"] = "missing-flows.json"
    report = prototype.check(data, FIXTURES)
    assert report["overall_status"] == "FAIL"


def test_missing_html_testid_fails():
    data = load()
    data["anchors"][0]["testid"] = "absent"
    report = prototype.check(data, FIXTURES)
    assert any(item["check_id"] == "html-testids" and item["status"] == "FAIL" for item in report["checks"])


def test_schema_invalid_is_rejected():
    data = load()
    data["kind"] = "powerpoint"
    report = prototype.check(data, FIXTURES)
    assert report["ok"] is False
    assert report["checks"][0]["status"] == "FAIL"


def test_accessibility_fail_is_fail():
    data = load()
    data["accessibility"]["keyboard"] = "FAIL"
    report = prototype.check(data, FIXTURES)
    assert report["overall_status"] == "FAIL"


def test_failed_check_entry_is_fail():
    data = load()
    data["checks"].append({"check_id": "clickthrough", "status": "FAIL", "detail": "button does nothing"})
    report = prototype.check(data, FIXTURES)
    assert report["overall_status"] == "FAIL"
