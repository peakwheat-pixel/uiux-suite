"""TASK-02: declared-scope inventory, baseline freeze and coverage mapping.

Under test:
- schema/semantic validation of inventories;
- deterministic baseline hashing and tamper detection;
- mapping stats where 100% only means declared-scope completeness;
- full_product_coverage stays UNKNOWN;
- high-risk gaps block the risk gate;
- scope shrinking / item deletion / high-risk re-labelling is detected;
- the CLI exposes validate/freeze/stats/check.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from uiux_engine import inventory
from uiux_engine.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "inventory" / "templates" / "new-manga-v134.json"


def _load():
    return inventory.load_inventory(TEMPLATE)


def _frozen():
    return inventory.freeze(_load(), reviewed_by="lead")


def _coverage_for(items: list[tuple[str, str]]) -> list[dict]:
    return [
        {"scenario_id": f"SC-{sid}", "scope_ref": sid, "test_state": state, "observed_runtime_level": "NATIVE_APP"}
        for sid, state in items
    ]


def test_template_loads_with_declared_scope():
    payload = _load()
    assert payload["inventory_id"] == "INV-NEW-MANGA-V134"
    assert len(payload["items"]) == 18
    assert sum(1 for item in payload["items"] if item["declared_scope"] == "included") == 15


def test_semantic_problems_are_detected(tmp_path):
    payload = _load()
    bad = copy.deepcopy(payload)
    bad["items"][0]["disposition"] = "excluded"  # included item cannot be excluded
    assert any("included item cannot be excluded" in problem for problem in inventory.semantic_problems(bad))

    bad = copy.deepcopy(payload)
    bad["items"][0]["disposition"] = "mapped"  # mapped requires evidence
    assert any("mapped item requires evidence_reference" in problem for problem in inventory.semantic_problems(bad))

    bad = copy.deepcopy(payload)
    high = next(item for item in bad["items"] if item["risk_level"] == "P0")
    high["applicability"] = "not_applicable"
    assert any("high-risk item must not be marked not_applicable" in problem for problem in inventory.semantic_problems(bad))


def test_baseline_freeze_and_tamper_detection():
    frozen = _frozen()
    assert len(frozen["scope"]["baseline_hash"]) == 64
    assert inventory.verify_baseline(frozen) == []
    # deterministic for the same content
    assert inventory.compute_baseline_hash(frozen) == frozen["scope"]["baseline_hash"]
    tampered = copy.deepcopy(frozen)
    tampered["items"][0]["risk_level"] = "P3"
    problems = inventory.verify_baseline(tampered)
    assert any("BASELINE_MISMATCH" in problem for problem in problems)


def test_stats_without_coverage_is_unmapped_and_gated():
    stats = inventory.mapping_stats(_frozen(), [])
    counts = stats["counts"]
    assert counts["total"] == 18
    assert counts["included"] == 15
    assert counts["mapped"] == 0
    assert stats["ratios"]["declared_scope_mapping_ratio"] == 0.0
    assert stats["full_product_coverage"] == "UNKNOWN"
    assert stats["risk_gate"]["blocked"] is True
    assert stats["risk_gate"]["blocking_items"]
    assert stats["gaps"]


def test_stats_with_partial_coverage():
    payload = _frozen()
    records = _coverage_for([
        ("ITM-PAGE-READER", "PASS"),
        ("ITM-PAGE-WORKBENCH", "PASS"),
        ("ITM-PAGE-SEARCH", "UNVERIFIED"),
    ])
    stats = inventory.mapping_stats(payload, records)
    counts = stats["counts"]
    assert counts["mapped"] == 3
    assert counts["verified"] == 2
    assert counts["unmapped"] == 12
    assert stats["ratios"]["declared_scope_mapping_ratio"] == round(3 / 15, 4)
    assert stats["risk_gate"]["blocked"] is True
    assert "ITM-PAGE-SEARCH" not in stats["risk_gate"]["blocking_items"]  # P2 not high risk
    assert "ITM-DIALOG-DELETE" in stats["risk_gate"]["blocking_items"]


def test_full_mapping_is_not_full_product_coverage():
    payload = _frozen()
    records = _coverage_for([(item["stable_id"], "PASS") for item in payload["items"] if item["declared_scope"] == "included"])
    stats = inventory.mapping_stats(payload, records)
    assert stats["ratios"]["declared_scope_mapping_ratio"] == 1.0
    assert stats["ratios"]["high_risk_verification_ratio"] == 1.0
    assert stats["full_product_coverage"] == "UNKNOWN"


def test_orphan_scope_refs_are_reported():
    payload = _frozen()
    records = _coverage_for([("ITM-PAGE-READER", "PASS")])
    records.append({"scenario_id": "SC-ORPHAN", "scope_ref": "ITM-NOT-IN-INVENTORY", "test_state": "PASS"})
    stats = inventory.mapping_stats(payload, records)
    assert stats["orphan_scope_refs"] == ["ITM-NOT-IN-INVENTORY"]


def test_scope_manipulation_is_detected():
    previous = _frozen()
    current = copy.deepcopy(previous)
    current["items"] = [item for item in current["items"] if item["stable_id"] != "ITM-CMD-PERMANENT-DELETE"]
    problems = inventory.scope_manipulation_check(current, previous)
    assert any("items removed" in problem for problem in problems)

    current = copy.deepcopy(previous)
    current["scope"]["excluded"].append("新增排除规则")
    problems = inventory.scope_manipulation_check(current, previous)
    assert any("exclusion rules added" in problem for problem in problems)

    current = copy.deepcopy(previous)
    high = next(item for item in current["items"] if item["stable_id"] == "ITM-DIALOG-DELETE")
    high["applicability"] = "not_applicable"
    problems = inventory.scope_manipulation_check(current, previous)
    assert any("re-labelled not_applicable" in problem for problem in problems)


def test_no_manipulation_for_identical_inventory():
    frozen = _frozen()
    assert inventory.scope_manipulation_check(copy.deepcopy(frozen), frozen) == []


def test_cli_inventory_validate_freeze_stats(tmp_path, capsys):
    assert cli_main(["inventory", "validate", "--inventory", str(TEMPLATE)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True

    out = tmp_path / "frozen.json"
    assert cli_main(["inventory", "freeze", "--inventory", str(TEMPLATE), "--out", str(out), "--reviewed-by", "lead"]) == 0
    capsys.readouterr()
    frozen = json.loads(out.read_text(encoding="utf-8"))
    assert frozen["scope"]["baseline_hash"]

    assert cli_main(["inventory", "stats", "--inventory", str(TEMPLATE)]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["full_product_coverage"] == "UNKNOWN"
    assert stats["ratios"]["declared_scope_mapping_ratio"] == 0.0


def test_cli_inventory_check_detects_tamper(tmp_path, capsys):
    frozen = _frozen()
    frozen_path = tmp_path / "frozen.json"
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False), encoding="utf-8")
    tampered = copy.deepcopy(frozen)
    tampered["items"][0]["risk_level"] = "P3"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    code = cli_main(["inventory", "check", "--inventory", str(tampered_path), "--previous", str(frozen_path)])
    assert code == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("BASELINE_MISMATCH" in item for item in payload["problems"])
