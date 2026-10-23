from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

from uiux_engine import contracts, rules


def test_catalog_is_schema_valid_and_unique():
    catalog = rules.load_catalog()
    assert contracts.validation_errors("rule-catalog", catalog) == []
    assert rules.semantic_problems(catalog) == []
    ids = [rule["rule_id"] for rule in catalog["rules"]]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 20


def test_all_rule_values_come_from_dictionary():
    catalog = rules.load_catalog()
    from uiux_engine import enums

    for rule in catalog["rules"]:
        assert rule["severity"] in enums.values("RuleSeverity")
        assert rule["category"] in enums.values("RuleCategory")
        assert rule["detector"] in enums.values("DetectorKind")
        assert set(rule["scope"]) <= set(enums.values("RuleScope"))
        assert rule["evidence_kind"] in enums.values("EvidenceKind")


def test_freeze_record_matches_catalog():
    assert rules.verify_frozen() == []
    assert rules.freeze_record()["rules_count"] == 20


def test_changed_catalog_breaks_freeze(tmp_path: Path):
    catalog = copy.deepcopy(rules.load_catalog())
    catalog["rules"][0]["title"] = "changed title"
    freeze_file = tmp_path / "freeze.json"
    freeze_file.write_text(json.dumps(rules.freeze_record(catalog)), encoding="utf-8")
    problems = rules.verify_frozen(freeze_file)
    assert any("sha256" in problem for problem in problems)


def test_duplicate_rule_id_is_rejected():
    catalog = copy.deepcopy(rules.load_catalog())
    catalog["rules"][1]["rule_id"] = catalog["rules"][0]["rule_id"]
    problems = rules.semantic_problems(catalog)
    assert any("duplicate rule_id" in problem for problem in problems)


def test_bad_severity_is_rejected():
    catalog = copy.deepcopy(rules.load_catalog())
    catalog["rules"][0]["severity"] = "WARNING"
    catalog["rules"][0]["category"] = "MADE_UP"
    assert rules.semantic_problems(catalog)


def valid_exemption() -> dict:
    return {
        "rule_id": "UX-SPACE-001",
        "scope": "src/legacy/**",
        "reason": "legacy layout frozen until Q2 migration",
        "owner": "design-system",
        "approved_by": "lead",
        "created_at": "2026-10-01T00:00:00+00:00",
        "expires_at": "2027-01-01T00:00:00+00:00",
        "ticket": "UX-123",
    }


def test_valid_exemption_passes():
    from uiux_engine.evidence import parse_time

    assert rules.check_exemption(valid_exemption(), now=parse_time("2026-10-24T00:00:00+00:00")) == []


def test_expired_exemption_is_rejected():
    from uiux_engine.evidence import parse_time

    exemption = valid_exemption()
    exemption["expires_at"] = "2026-01-01T00:00:00+00:00"
    problems = rules.check_exemption(exemption, now=parse_time("2026-10-24T00:00:00+00:00"))
    assert any("expired" in problem for problem in problems)


def test_unknown_rule_and_reversed_dates_are_rejected():
    from uiux_engine.evidence import parse_time

    exemption = valid_exemption()
    exemption["rule_id"] = "UX-NOPE-999"
    exemption["created_at"] = "2027-01-01T00:00:00+00:00"
    exemption["expires_at"] = "2026-01-01T00:00:00+00:00"
    problems = rules.check_exemption(exemption, now=parse_time("2026-10-24T00:00:00+00:00"))
    assert any("unknown rule_id" in problem for problem in problems)
    assert any("created_at" in problem for problem in problems)


def test_rules_cli_reports_frozen_catalog():
    env = {"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "uiux_engine.cli", "rules"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**__import__("os").environ, **env},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["rules_count"] == 20
    assert payload["frozen"] is True
