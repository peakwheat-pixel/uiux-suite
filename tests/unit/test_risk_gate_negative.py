"""TASK-01 negative / fault-injection tests for the V1.3.5 risk gate.

Each case injects a violation and asserts the gate fails or blocks. The tests
must fail if the checker regresses to an always-true or lenient implementation.
"""
from __future__ import annotations

import copy
import json

import pytest

from uiux_engine import risk_gate

HEX = "a" * 64
FROZEN = "b" * 64


def inventory(n_high: int = 2) -> dict:
    items = [
        {
            "stable_id": f"ITM-HR-{i}",
            "declared_scope": "included",
            "risk_level": "P0" if i == 0 else "P1",
        }
        for i in range(n_high)
    ]
    items.append({"stable_id": "ITM-NORMAL", "declared_scope": "included", "risk_level": "P3"})
    items.append({"stable_id": "ITM-EXCLUDED", "declared_scope": "excluded", "risk_level": "P1"})
    return {"items": items, "scope": {"baseline_hash": FROZEN}}


def evidence() -> list[dict]:
    return [{"id": "EV-1", "status": "AVAILABLE", "source_sha256": HEX},
            {"id": "EV-2", "status": "AVAILABLE", "source_sha256": "c" * 64}]


def record(index: int = 0, **updates) -> dict:
    base = {
        "scenario_id": f"S-{index}",
        "scope_ref": f"ITM-HR-{index}",
        "test_state": "PASS",
        "required_runtime_level": "NATIVE_APP",
        "observed_runtime_level": "NATIVE_APP",
        "action": "import_execute",
        "execution_mode": "ISOLATED",
        "backup_verified": True,
        "restore_verified": True,
        "restore_consistent": True,
        "evidence_refs": ["EV-1"],
    }
    base.update(updates)
    return base


def good_inputs() -> tuple[dict, list[dict], list[dict]]:
    return inventory(), [record(0), record(1)], evidence()


def run(inv=None, records=None, ev=None, **kwargs) -> dict:
    i, r, e = good_inputs()
    return risk_gate.evaluate(
        inventory=inv if inv is not None else i,
        coverage_records=records if records is not None else r,
        evidence=ev if ev is not None else e,
        **kwargs,
    )


def codes(verdict: dict) -> str:
    return " | ".join(verdict.get("violations", []))


# ------------------------------------------------------------------ baseline
def test_clean_input_passes_and_reports_coverage():
    verdict = run()
    assert verdict["gate_status"] == "PASS"
    assert verdict["integrity_status"] == "PASS"
    assert verdict["execution_coverage"]["high_risk_total"] == 2
    assert verdict["execution_coverage"]["high_risk_verified"] == 2
    assert verdict["execution_coverage"]["ratio"] == 1.0
    assert verdict["a_level_risk_met"] is True


# ------------------------------------------------------- injected violations
def test_missing_high_risk_item_fails():
    verdict = run(records=[record(0)])
    assert verdict["gate_status"] == "FAIL"
    assert "ITM-HR-1" in codes(verdict)


def test_undeclared_high_risk_scope_fails():
    rec = record(2, scope_ref="ITM-UNREGISTERED", action="permanent_delete")
    verdict = run(records=[record(0), record(1), rec])
    assert verdict["gate_status"] == "FAIL"
    assert "UNDECLARED_SCOPE" in codes(verdict)


def test_pass_without_evidence_fails():
    verdict = run(records=[record(0, evidence_refs=[]), record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "PASS_WITHOUT_EVIDENCE" in codes(verdict)


def test_dangling_evidence_fails():
    verdict = run(records=[record(0, evidence_refs=["EV-MISSING"]), record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "DANGLING_EVIDENCE" in codes(verdict)


def test_evidence_hash_mismatch_fails():
    verdict = run(evidence_hash_resolver=lambda ref: "0" * 64)
    assert verdict["gate_status"] == "FAIL"
    assert "EVIDENCE_HASH_MISMATCH" in codes(verdict)


def test_unverified_marked_as_pass_fails():
    rec = record(0, test_state="UNVERIFIED", disposition="AUDITOR_OMISSION",
                 pass_marker=True, verified=True)
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "UNVERIFIED_MARKED_AS_PASS" in codes(verdict)


def test_readonly_claimed_as_isolated_fails():
    rec = record(0, execution_mode="READONLY")
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "READONLY_CLAIMED_FOR_WRITE_ACTION" in codes(verdict)
    assert "WRITE_ACTION_NOT_ISOLATED" in codes(verdict)


def test_isolated_without_backup_fails():
    rec = record(0, backup_verified=False)
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "ISOLATED_WITHOUT_VERIFIED_BACKUP" in codes(verdict)


def test_isolated_without_restore_fails():
    rec = record(0, restore_verified=False)
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "ISOLATED_WITHOUT_VERIFIED_RESTORE" in codes(verdict)


def test_restore_inconsistent_fails():
    rec = record(0, restore_consistent=False)
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "RESTORE_INCONSISTENT" in codes(verdict)


def test_simulated_claimed_native_fails():
    rec = record(0, observed_runtime_level="SIMULATED")
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "EVIDENCE_LEVEL_BELOW_REQUIRED" in codes(verdict)


def test_scope_shrink_detected_by_frozen_baseline():
    inv = inventory()
    inv["scope"]["baseline_hash"] = "0" * 64
    verdict = run(inv=inv, frozen_baseline_hash=FROZEN)
    assert verdict["gate_status"] == "FAIL"
    assert "scope_baseline_unchanged" in codes(verdict)


def test_not_applicable_abuse_fails():
    inv = inventory()
    inv["items"][0]["declared_scope"] = "included"  # executable path hidden as N/A
    rec = record(0, test_state="NOT_APPLICABLE", disposition="NOT_APPLICABLE",
                 execution_mode=None, backup_verified=False, restore_verified=False,
                 evidence_refs=["EV-1"])
    verdict = run(inv=inv, records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "NOT_APPLICABLE" in codes(verdict)


def test_reviewer_conflict_blocks_or_fails():
    verdict = run(reviewer_findings={"conflicts": [{"id": "VF-X", "detail": "auditor PASS contradicted"}]})
    assert verdict["gate_status"] in ("FAIL", "BLOCKED")
    assert "REVIEWER_CONFLICT" in codes(verdict)


def test_empty_inventory_blocks():
    verdict = run(inv={"items": [], "scope": {"baseline_hash": FROZEN}})
    assert verdict["gate_status"] == "BLOCKED"
    assert "INVENTORY_EMPTY" in codes(verdict)


def test_malformed_coverage_blocks():
    verdict = run(records=[{"scenario_id": "S"}])
    assert verdict["gate_status"] == "BLOCKED"
    assert "COVERAGE_RECORD_WITHOUT_SCOPE" in codes(verdict)


def test_non_list_evidence_blocks():
    verdict = run(ev=12345)
    assert verdict["gate_status"] == "BLOCKED"


def test_risk_plan_mismatch_fails():
    plan = {"items": [{"id": "R-1", "action": "import_execute", "mode": "ISOLATED",
                       "risk_level": "P0", "scope_ref": "ITM-NOT-IN-INVENTORY"}]}
    verdict = run(risk_plan=plan)
    assert verdict["gate_status"] == "FAIL"
    assert "risk_plan_matches_inventory" in codes(verdict)


def test_unverified_without_disposition_fails_in_strict_mode():
    rec = record(0, test_state="UNVERIFIED", disposition=None, evidence_refs=["EV-1"])
    verdict = run(records=[rec, record(1)])
    assert verdict["gate_status"] == "FAIL"
    assert "UNVERIFIED_WITHOUT_DISPOSITION" in codes(verdict)


# ------------------------------------------------------- legacy compatibility
def test_legacy_v134_input_still_evaluates_with_old_semantics():
    """V1.3.4 records have no mode/backup fields; legacy mode must not require them."""
    legacy_records = [
        {"scenario_id": "S1", "scope_ref": "ITM-HR-0", "test_state": "PASS",
         "required_runtime_level": "SIMULATED", "observed_runtime_level": "NATIVE_APP",
         "evidence_refs": ["EV-1"]},
        {"scenario_id": "S2", "scope_ref": "ITM-HR-1", "test_state": "UNVERIFIED",
         "required_runtime_level": "SIMULATED", "observed_runtime_level": "NONE",
         "disposition": "NATIVE_INTERACTION_UNAVAILABLE", "evidence_refs": ["EV-1"]},
    ]
    verdict = risk_gate.evaluate(inventory(), legacy_records, evidence(), schema_version="1.3.4")
    assert verdict["gate_status"] == "PASS"
    assert verdict["execution_coverage"]["high_risk_total"] == 2
    assert verdict["execution_coverage"]["high_risk_verified"] == 1
    assert verdict["execution_coverage"]["ratio"] == 0.5
    assert verdict["a_level_risk_met"] is False


def test_legacy_input_cannot_hide_evidence_problems():
    legacy = [{"scenario_id": "S1", "scope_ref": "ITM-HR-0", "test_state": "PASS",
               "required_runtime_level": "SIMULATED", "observed_runtime_level": "NATIVE_APP",
               "evidence_refs": ["EV-MISSING"]}]
    verdict = risk_gate.evaluate(inventory(), legacy, evidence(), schema_version="1.3.4")
    assert verdict["gate_status"] == "FAIL"


def test_unsupported_version_blocks():
    verdict = run(schema_version="9.9.9")
    assert verdict["gate_status"] == "BLOCKED"
    assert "SCHEMA_VERSION_UNSUPPORTED" in codes(verdict)


def test_vacuous_guard_no_longer_present():
    """The previous bug was `... or True`; ensure no such expression exists."""
    import inspect
    source = inspect.getsource(risk_gate)
    assert "or True" not in source
    assert "no_fake_high_risk_pass" not in source
