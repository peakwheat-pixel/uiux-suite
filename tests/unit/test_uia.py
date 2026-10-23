from __future__ import annotations

import pytest

import json
from pathlib import Path

from conftest import REPO_ROOT

from uiux_engine import uia

REAL = REPO_ROOT / "evidence" / "T3.4" / "uia-probe.json"


def element(control_type="ControlType.Button", name="OK", width=44, height=44, offscreen=False, children=None) -> dict:
    return {
        "name": name,
        "control_type": control_type,
        "automation_id": "auto-1",
        "class_name": "Button",
        "is_enabled": True,
        "is_offscreen": offscreen,
        "is_keyboard_focusable": True,
        "bounds": {"x": 0, "y": 0, "width": width, "height": height},
        "children": children or [],
    }


def dump(*elements: dict) -> dict:
    return {"runtime_level": "NATIVE_UIA", "elements": list(elements)}


def test_clean_tree_has_no_findings():
    report = uia.findings(dump(element()))
    assert report["ok"] is True
    assert report["findings"] == []


def test_missing_name_is_a11y_fail():
    report = uia.findings(dump(element(name="")))
    assert report["ok"] is False
    assert report["findings"][0]["rule_id"] == "UX-A11Y-001"
    assert report["findings"][0]["severity"] == "FAIL"


def test_small_target_is_flagged():
    report = uia.findings(dump(element(width=20, height=44)))
    assert any(finding["rule_id"] == "UX-SPACE-002" for finding in report["findings"])


def test_offscreen_interactive_is_flagged():
    report = uia.findings(dump(element(offscreen=True)))
    assert any(finding["rule_id"] == "UX-GEOM-001" for finding in report["findings"])


def test_nested_children_are_walked():
    parent = element(children=[element(name="")])
    report = uia.findings(dump(parent))
    assert report["element_count"] == 2
    assert any(finding["rule_id"] == "UX-A11Y-001" for finding in report["findings"])


def test_non_interactive_missing_name_is_ignored():
    report = uia.findings(dump(element(control_type="ControlType.Text", name="")))
    assert report["findings"] == []


def test_real_native_evidence_is_parseable():
    if not REAL.is_file():
        pytest.skip("native evidence not present; run scripts/collect_uia_evidence.ps1 first")
    data = json.loads(REAL.read_text(encoding="utf-8"))
    assert data["runtime_level"] == "NATIVE_UIA"
    report = uia.findings(data)
    assert report["element_count"] >= 10
    assert report["runtime_level"] == "NATIVE_UIA"


def test_rule_ids_exist_in_catalog():
    from uiux_engine import rules

    known = {rule["rule_id"] for rule in rules.load_catalog()["rules"]}
    assert set(uia.SEVERITY) <= known
