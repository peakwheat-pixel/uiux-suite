"""TASK-04 attribution + TASK-05 high-risk gating regression."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uiux_engine import attribution, riskflow

AUDIT = Path(r"G:\AI\uiux-v134\evidence\audit\v134")
ISSUES = AUDIT / "issues.json"


def _good_p1() -> dict:
    return {
        "id": "I-1",
        "severity": "P1",
        "title": "t",
        "attribution": "PRODUCT",
        "disposition": "CONFIRMED",
        "evidence_refs": ["a.json"],
        "reproduction": "steps",
        "root_cause": "utf8->gbk",
        "impact": "titles unreadable",
        "verification": "DOM hit",
    }


def test_valid_p1_issue_passes():
    assert attribution.validate_issue(_good_p1()) == []


def test_p0p1_missing_fields_are_rejected():
    issue = _good_p1()
    del issue["root_cause"]
    problems = attribution.validate_issue(issue)
    assert any("missing P0/P1" in p for p in problems)


def test_product_requires_evidence():
    issue = _good_p1()
    issue["evidence_refs"] = []
    assert any("PRODUCT attribution requires evidence" in p for p in attribution.validate_issue(issue))


def test_confirmed_environment_is_rejected():
    issue = _good_p1()
    issue["attribution"] = "ENVIRONMENT"
    assert any("confirmed findings cannot be" in p for p in attribution.validate_issue(issue))


def test_classify_rules():
    assert attribution.classify(has_evidence=False) == "UNCERTAIN"
    assert attribution.classify(has_evidence=True, environment_only=True) == "ENVIRONMENT"
    assert attribution.classify(has_evidence=True, captured=False) == "AUDITOR_OMISSION"
    assert attribution.classify(has_evidence=True, product_signal=True) == "PRODUCT"
    assert attribution.classify(has_evidence=True) == "UNCERTAIN"


def test_reviewer_retraction_excludes_confirmed_count():
    issues = {"issues": [_good_p1(), dict(_good_p1(), id="I-2")]}
    stats_before = attribution.attribution_stats(issues["issues"])
    merged = attribution.merge_with_reviewer(issues, {"VF-X": ["I-2"]})
    stats_after = attribution.attribution_stats(merged["issues"])
    assert stats_before["confirmed"] == 2
    assert stats_after["confirmed"] == 1
    assert merged["reviewer_retractions"] == ["I-2"]


def test_real_issues_pass_lint():
    if not ISSUES.is_file():
        pytest.skip("Phase A audit issues not present")
    payload = json.loads(ISSUES.read_text(encoding="utf-8"))
    problems = attribution.lint_issues(payload)
    assert problems == [], problems


def _plan() -> dict:
    return {
        "schema_version": "1.3.4",
        "plan_id": "RISK-V134-A",
        "items": [
            {"id": "R-01", "action": "permanent_delete", "mode": "READONLY",
             "evidence_requirement": "screenshot + DOM + undo check"},
            {"id": "R-02", "action": "import_execute", "mode": "ISOLATED",
             "target_sandbox": "sandbox/run-risk", "backup_plan": "backup", "restore_plan": "restore",
             "evidence_requirement": "before/after DB hashes + screenshots"},
        ],
    }


def test_plan_validation():
    assert riskflow.validate_plan(_plan()) == []
    broken = _plan()
    del broken["items"][1]["backup_plan"]
    assert any("backup_plan" in p for p in riskflow.validate_plan(broken))
    broken = _plan()
    broken["items"][0]["mode"] = "UNKNOWN"
    assert any("invalid mode" in p for p in riskflow.validate_plan(broken))


def test_readonly_never_passes_high_risk():
    assert not riskflow.can_mark_pass({"mode": "READONLY", "executed": True, "evidence_refs": ["e"], "backup_verified": True, "restore_verified": True})
    assert not riskflow.can_mark_pass({"mode": "ISOLATED", "executed": False, "evidence_refs": ["e"], "backup_verified": True, "restore_verified": True})
    assert not riskflow.can_mark_pass({"mode": "ISOLATED", "executed": True, "evidence_refs": ["e"], "backup_verified": False, "restore_verified": True})
    assert riskflow.can_mark_pass({"mode": "ISOLATED", "executed": True, "evidence_refs": ["e"], "backup_verified": True, "restore_verified": True})


def test_evaluate_plan_keeps_unverified_with_reason():
    result = riskflow.evaluate_plan(_plan(), [])
    assert result["summary"]["pass"] == 0
    assert result["summary"]["unverified"] == 2
    assert all(item["reason_code"] for item in result["items"])
