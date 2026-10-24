"""TASK-08: report facts and linter regression cases."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from uiux_engine import report_facts
from uiux_engine.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(r"G:\AI\uiux-v134\evidence\audit\v134")
VERIFY = Path(r"G:\AI\uiux-v134\evidence\verify")


def _facts() -> dict:
    return {
        "schema_version": "1.3.4",
        "run_id": "r1",
        "counts": {
            "coverage_records": 10,
            "pass_records": 6,
            "unverified_records": 4,
            "evidence_items": 20,
            "unverified_scopes": 4,
            "high_risk_unverified": 2,
            "resolved_evidence_refs": 8,
            "dangling_evidence_refs": 0,
        },
        "claims": [{"claim_id": "C-01", "statement": "x", "evidence": ["a.json"], "status": "SUPPORTED"}],
        "level_claim": {"declared": "B", "a_level_eligible": False, "reasons": []},
    }


def test_clean_facts_pass_lint():
    assert report_facts.lint(_facts()) == []


def test_dangling_evidence_is_rejected():
    facts = _facts()
    facts["counts"]["dangling_evidence_refs"] = 2
    assert any("DANGLING_EVIDENCE_REF" in p for p in report_facts.lint(facts))


def test_unverified_without_disposition_is_rejected():
    facts = _facts()
    facts["counts"]["unverified_scopes"] = 0
    assert any("UNVERIFIED_WITHOUT_DISPOSITION" in p for p in report_facts.lint(facts))


def test_unsupported_claim_is_rejected():
    facts = _facts()
    facts["claims"].append({"claim_id": "C-09", "statement": "y", "evidence": ["b.json"], "status": "UNSUPPORTED"})
    assert any("UNSUPPORTED_CLAIM" in p for p in report_facts.lint(facts))


def test_level_overclaim_is_rejected():
    facts = _facts()
    facts["level_claim"]["a_level_eligible"] = True
    assert any("LEVEL_OVERCLAIM" in p for p in report_facts.lint(facts))


def test_capture_coverage_mismatch_is_rejected():
    facts = _facts()
    facts["counts"]["captures"] = 3
    facts["counts"]["coverage_records"] = 10
    assert any("CAPTURE_COVERAGE_MISMATCH" in p for p in report_facts.lint(facts))


def test_g6_overclaim_is_rejected(tmp_path):
    facts = _facts()
    (tmp_path / "task-result.json").write_text(
        json.dumps({"run_id": "r1", "derived_g6": {"state": "PASS"}}), encoding="utf-8"
    )
    assert any("G6_OVERCLAIM" in p for p in report_facts.lint(facts, tmp_path))


@pytest.mark.skipif(not (AUDIT / "task-result.json").is_file(), reason="Phase A audit evidence not present")
def test_real_phase_a_facts_lint_clean(tmp_path):
    facts = report_facts.build_facts(AUDIT, VERIFY, ROOT / "inventory" / "templates" / "new-manga-v134.json")
    assert facts["counts"]["coverage_records"] > 0
    assert facts["counts"]["high_risk_unverified"] >= 8
    assert facts["level_claim"]["a_level_eligible"] is False
    problems = report_facts.lint(facts, AUDIT)
    assert problems == [], problems
    out = tmp_path / "facts.json"
    assert cli_main(["facts", "--audit-dir", str(AUDIT), "--verify-dir", str(VERIFY), "--out", str(out)]) == 0
    assert out.is_file()
    assert cli_main(["lint", "--facts", str(out), "--audit-dir", str(AUDIT)]) == 0
