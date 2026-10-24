"""TASK-05: A/B environment-attribution regression against the historical cases.

Seven known V1.3.4 environment traps are replayed through the frozen
`classify_ab_attribution` contract. Environment-authored failures must never
become product P0/P1; shared or product-signalled classes must stay eligible for
defect classification. This is a contract-level regression, not a new UI run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uiux_engine import fixture

OUT = Path(r"G:\AI\uiux-v135\evidence\task05")

CASES = [
    {
        "case": "managed_root_misplacement",
        "description": "managed root points at the old absolute path after sandbox copy",
        "bad": [{"class": "readonly_violation", "code": "READONLY_VIOLATION"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
    {
        "case": "preview_namespace_lock",
        "description": "derived/.preview-lifecycle.lock still bound to the old derived root",
        "bad": [{"class": "fixture_invalid", "code": "FIXTURE_INVALID"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
    {
        "case": "derived_root_mismatch",
        "description": "namespace binding identity mismatch after root relocation",
        "bad": [{"class": "data_root_missing", "code": "SANDBOX_ROOT_UNRESOLVED"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
    {
        "case": "catalog_identity_mismatch",
        "description": "catalog.sqlite preview_namespace still binds the old file identity",
        "bad": [{"class": "fixture_invalid", "code": "FIXTURE_INVALID"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
    {
        "case": "resource_missing",
        "description": "packaged sidecar resource missing from the copied sandbox",
        "bad": [{"class": "missing_executable", "code": "EXECUTABLE_MISSING"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
    {
        "case": "data_incomplete",
        "description": "fixture data root incomplete after copy",
        "bad": [{"class": "data_root_missing", "code": "SANDBOX_ROOT_UNRESOLVED"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
    {
        "case": "core_start_failure",
        "description": "core sidecar fails to start inside the sandbox",
        "bad": [{"class": "missing_env", "code": "ENV_VAR_MISSING"}],
        "good": [],
        "product_signal": False,
        "expected": "ENVIRONMENT",
    },
]


def _classify(case: dict) -> dict:
    return fixture.classify_ab_attribution(
        bad_problems=[dict(item) for item in case["bad"]],
        good_problems=[dict(item) for item in case["good"]],
        product_signal=case["product_signal"],
    )


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_historical_environment_cases_are_environment_authored(case):
    result = _classify(case)
    assert result["environment_authored"] is True
    assert result["product_defect_eligible"] is False
    assert result["environment_only_classes"]


def test_shared_failure_class_is_not_blamed_on_environment():
    case = {"bad": [{"class": "fixture_invalid", "code": "FIXTURE_INVALID"}],
            "good": [{"class": "fixture_invalid", "code": "FIXTURE_INVALID"}],
            "product_signal": False}
    result = _classify(case)
    assert result["environment_authored"] is False
    assert result["product_defect_eligible"] is True


def test_product_signal_keeps_defect_eligible():
    case = {"bad": [{"class": "data_root_missing", "code": "SANDBOX_ROOT_UNRESOLVED"}],
            "good": [], "product_signal": True}
    result = _classify(case)
    assert result["environment_authored"] is False
    assert result["product_defect_eligible"] is True


def test_failure_class_matrix_covers_seven_classes():
    matrix = fixture.failure_class_matrix()
    classes = {row["class"] for row in matrix}
    assert classes == set(fixture.FAILURE_CLASSES)
    assert len(matrix) == 7
    for row in matrix:
        assert row["code"]


def test_ab_regression_evidence_is_reproducible():
    rows = []
    for case in CASES:
        result = _classify(case)
        rows.append({
            "case": case["case"],
            "description": case["description"],
            "bad_classes": result["bad_classes"],
            "good_classes": result["good_classes"],
            "environment_authored": result["environment_authored"],
            "product_defect_eligible": result["product_defect_eligible"],
            "expected": case["expected"],
            "verdict": "PASS" if result["environment_authored"] else "FAIL",
        })
    payload = {
        "schema_version": "1.3.5",
        "kind": "ab_attribution_regression",
        "cases": rows,
        "summary": {
            "cases": len(rows),
            "environment_classified": len([r for r in rows if r["environment_authored"]]),
            "product_eligible": len([r for r in rows if r["product_defect_eligible"]]),
            "failures": len([r for r in rows if r["verdict"] == "FAIL"]),
        },
        "source_evidence": "G:\\AI\\uiux-v134\\evidence\\audit\\PILOT_RUN_NOTES.md",
        "note": "replay of the frozen A/B contract; does not re-run the historical pilot",
    }
    assert payload["summary"]["failures"] == 0
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "ab-regression.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        # The acceptance evidence root only exists on the audit host; CI runners
        # cannot create it. The contract assertions above already ran.
        pytest.skip("acceptance evidence root unavailable in this environment")
