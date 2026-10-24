"""TASK-07: V1.3.5 release facts lint semantics (positive + negative)."""
from __future__ import annotations

import copy

import pytest

from uiux_engine import report_facts


def clean() -> dict:
    return {
        "schema_version": "1.3.5",
        "kind": "release_facts",
        "counts": {
            "high_risk_total": 10, "risk_gate_integrity": "PASS",
            "dangling_evidence_refs": 0, "coverage_pass": 8, "coverage_unverified": 8,
        },
        "separation": {
            "mechanism": "PASS",
            "business_high_risk": {"verified": 3, "total": 10, "ratio": 0.3},
            "readonly_records": 8, "executed_records": 2,
        },
        "claims": [
            {"claim_id": "RF-01", "kind": "mechanism", "statement": "mechanism evaluated", "status": "SUPPORTED", "evidence": ["risk.json"]},
            {"claim_id": "RF-02", "kind": "separation", "statement": "business separated", "status": "SUPPORTED", "evidence": ["risk.json"]},
            {"claim_id": "RF-03", "kind": "readonly", "statement": "readonly separated", "status": "SUPPORTED", "evidence": ["cov.json"]},
            {"claim_id": "RF-04", "kind": "evidence", "statement": "evidence resolvable", "status": "SUPPORTED", "evidence": ["m.json"]},
            {"claim_id": "RF-05", "kind": "level", "statement": "level derived", "status": "SUPPORTED", "evidence": ["risk.json"]},
        ],
        "level_claim": {"declared": "B", "a_level_eligible": False, "reasons": []},
        "tests_total": 574,
    }


def test_clean_facts_pass():
    assert report_facts.lint_release_facts(clean()) == []


def test_empty_facts_fail_closed():
    assert report_facts.lint_release_facts({})  # non-empty problems


def test_mechanism_not_pass():
    facts = clean(); facts["separation"]["mechanism"] = "FAIL"
    assert any("MECHANISM_NOT_PASS" in p for p in report_facts.lint_release_facts(facts))


def test_level_overclaim():
    facts = clean(); facts["level_claim"]["a_level_eligible"] = True
    assert any("LEVEL_OVERCLAIM" in p for p in report_facts.lint_release_facts(facts))


def test_dangling_evidence_level_overclaim():
    facts = clean(); facts["counts"]["dangling_evidence_refs"] = 2; facts["level_claim"]["a_level_eligible"] = True
    problems = report_facts.lint_release_facts(facts)
    assert any("dangling" in p.lower() for p in problems)


def test_unsupported_claim():
    facts = clean(); facts["claims"].append({"claim_id": "RF-99", "kind": "mechanism", "statement": "x", "status": "UNSUPPORTED", "evidence": ["e"]})
    assert any("UNSUPPORTED_CLAIM" in p for p in report_facts.lint_release_facts(facts))


def test_claim_without_evidence():
    facts = clean(); facts["claims"][0]["evidence"] = []
    assert any("CLAIM_WITHOUT_EVIDENCE" in p for p in report_facts.lint_release_facts(facts))


def test_readonly_as_executed():
    facts = clean()
    facts["separation"]["executed_records"] = 0
    facts["claims"].append({"claim_id": "RF-98", "kind": "readonly_as_executed", "statement": "readonly proves execution", "status": "SUPPORTED", "evidence": ["e"]})
    assert any("READONLY_AS_EXECUTED" in p for p in report_facts.lint_release_facts(facts))


def test_mechanism_overclaim():
    facts = clean()
    facts["claims"].append({"claim_id": "RF-97", "kind": "business_done", "statement": "all high-risk flows passed", "status": "SUPPORTED", "evidence": ["e"]})
    assert any("MECHANISM_OVERCLAIM" in p for p in report_facts.lint_release_facts(facts))


def test_legacy_inheritance():
    facts = clean()
    facts["claims"].append({"claim_id": "RF-96", "kind": "legacy", "statement": "v1.3.4 result inherited", "status": "SUPPORTED", "evidence": ["e"]})
    assert any("LEGACY_INHERITANCE" in p for p in report_facts.lint_release_facts(facts))
