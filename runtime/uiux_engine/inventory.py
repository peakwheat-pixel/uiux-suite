"""Declared-scope inventory and coverage mapping (TASK-02, V1.3.4).

Design rules:
- The inventory is data: stable ids, risk levels, applicability, discovery source
  and declared scope (included/excluded) are declared, then frozen by hash.
- "100%" only ever means *declared-scope mapping completeness*; full-product
  coverage is UNKNOWN unless complete independent evidence exists.
- Deleting items, shrinking the declared scope or re-labelling high-risk items as
  not applicable is detected as SCOPE_MANIPULATION.
- Mapping to coverage records uses the optional V1.3.4 ``scope_ref`` field.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

PACKAGE_DIR = Path(__file__).resolve().parent
SUITE_ROOT = PACKAGE_DIR.parent.parent
INVENTORY_SCHEMA_PATH = SUITE_ROOT / "inventory" / "schema" / "inventory.v1.schema.json"
INVENTORY_SCHEMA_VERSION = "1.0"
TYPE_VALUES = ("page", "region", "dialog", "menu", "flow", "entrypoint", "state_machine", "command")
RISK_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
HIGH_RISK = {"P0", "P1"}


class InventoryError(ValueError):
    """Raised when an inventory cannot be loaded or is semantically invalid."""


def _schema() -> dict[str, Any]:
    return json.loads(INVENTORY_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_inventory(path: str | Path) -> dict[str, Any]:
    inventory_path = Path(path)
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InventoryError(f"INVENTORY_INVALID: cannot read {inventory_path}: {exc}") from exc
    errors = sorted(jsonschema.Draft202012Validator(_schema()).iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        raise InventoryError(f"INVENTORY_INVALID: {list(first.absolute_path)}: {first.message}")
    problems = semantic_problems(payload)
    if problems:
        raise InventoryError("INVENTORY_INVALID: " + "; ".join(problems))
    return payload


def semantic_problems(inventory: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    items = inventory.get("items", [])
    ids = [item.get("stable_id") for item in items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate stable_id")
    for item in items:
        scope = item.get("declared_scope")
        disposition = item.get("disposition")
        if scope == "included" and disposition == "excluded":
            problems.append(f"{item.get('stable_id')}: included item cannot be excluded")
        if scope == "excluded" and disposition != "excluded":
            problems.append(f"{item.get('stable_id')}: excluded item must use excluded disposition")
        if disposition == "mapped" and not item.get("evidence_reference"):
            problems.append(f"{item.get('stable_id')}: mapped item requires evidence_reference")
        if item.get("risk_level") in HIGH_RISK and item.get("applicability") == "not_applicable":
            problems.append(f"{item.get('stable_id')}: high-risk item must not be marked not_applicable")
    scope = inventory.get("scope", {})
    included_rules = scope.get("included") or []
    excluded_rules = scope.get("excluded") or []
    if not included_rules:
        problems.append("declared scope must include at least one included rule")
    if set(included_rules) & set(excluded_rules):
        problems.append("included and excluded rules must be disjoint")
    return problems


def canonical_payload(inventory: dict[str, Any]) -> dict[str, Any]:
    items = sorted(
        (
            {
                "stable_id": item["stable_id"],
                "type": item["type"],
                "risk_level": item["risk_level"],
                "applicability": item["applicability"],
                "discovery_source": item["discovery_source"],
                "declared_scope": item["declared_scope"],
                "disposition": item["disposition"],
            }
            for item in inventory.get("items", [])
        ),
        key=lambda item: item["stable_id"],
    )
    scope = inventory.get("scope", {})
    return {
        "inventory_id": inventory.get("inventory_id"),
        "declared_scope_id": scope.get("declared_scope_id"),
        "included": sorted(scope.get("included") or []),
        "excluded": sorted(scope.get("excluded") or []),
        "source_binding": scope.get("source_binding") or {},
        "items": items,
    }


def compute_baseline_hash(inventory: dict[str, Any]) -> str:
    payload = canonical_payload(inventory)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze(inventory: dict[str, Any], *, reviewed_by: str | None = None) -> dict[str, Any]:
    frozen = json.loads(json.dumps(inventory, ensure_ascii=False))
    frozen["scope"]["baseline_hash"] = compute_baseline_hash(frozen)
    if reviewed_by:
        frozen["scope"]["reviewed_by"] = reviewed_by
    return frozen


def verify_baseline(inventory: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    declared = inventory.get("scope", {}).get("baseline_hash")
    if not declared:
        problems.append("BASELINE_MISSING: scope.baseline_hash is required before mapping")
        return problems
    actual = compute_baseline_hash(inventory)
    if declared != actual:
        problems.append(f"BASELINE_MISMATCH: declared {declared} != recomputed {actual}")
    return problems


def _records_by_scope_ref(coverage_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in coverage_records:
        scope_ref = record.get("scope_ref")
        if scope_ref:
            grouped.setdefault(scope_ref, []).append(record)
    return grouped


def map_coverage(
    inventory: dict[str, Any],
    coverage_records: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped = _records_by_scope_ref(coverage_records)
    included = [item for item in inventory["items"] if item["declared_scope"] == "included"]
    excluded = [item for item in inventory["items"] if item["declared_scope"] == "excluded"]
    mapped: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    verified: list[str] = []
    unverified: list[str] = []
    for item in included:
        records = grouped.get(item["stable_id"], [])
        if not records:
            if item["disposition"] == "mapped":
                unmapped.append({"stable_id": item["stable_id"], "reason": "MAPPED_WITHOUT_RECORD"})
            else:
                unmapped.append({"stable_id": item["stable_id"], "reason": "NOT_MAPPED"})
            continue
        mapped.append({"stable_id": item["stable_id"], "records": len(records)})
        if any(record.get("test_state") == "PASS" for record in records):
            verified.append(item["stable_id"])
        else:
            unverified.append(item["stable_id"])
    orphans = sorted(set(grouped) - {item["stable_id"] for item in inventory["items"]})
    return {
        "mapped": mapped,
        "unmapped": unmapped,
        "verified": verified,
        "unverified": unverified,
        "orphan_scope_refs": orphans,
        "excluded": [item["stable_id"] for item in excluded],
    }


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def mapping_stats(
    inventory: dict[str, Any],
    coverage_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mapping = map_coverage(inventory, coverage_records or [])
    included = [item for item in inventory["items"] if item["declared_scope"] == "included"]
    excluded = [item for item in inventory["items"] if item["declared_scope"] == "excluded"]
    high_risk = [item for item in included if item["risk_level"] in HIGH_RISK]
    high_risk_verified = [item["stable_id"] for item in high_risk if item["stable_id"] in mapping["verified"]]
    high_risk_blocking = [
        item["stable_id"]
        for item in high_risk
        if item["stable_id"] not in mapping["verified"]
    ]
    mapped_ids = {entry["stable_id"] for entry in mapping["mapped"]}
    verified_ids = set(mapping["verified"])
    counts = {
        "total": len(inventory["items"]),
        "included": len(included),
        "excluded": len(excluded),
        "mapped": len(mapped_ids),
        "unmapped": len(included) - len(mapped_ids),
        "verified": len(verified_ids),
        "unverified": len(mapped_ids - verified_ids),
        "high_risk": len(high_risk),
        "high_risk_verified": len(high_risk_verified),
    }
    return {
        "inventory_id": inventory["inventory_id"],
        "declared_scope_id": inventory["scope"]["declared_scope_id"],
        "baseline_hash": inventory["scope"].get("baseline_hash"),
        "counts": counts,
        "ratios": {
            "declared_scope_mapping_ratio": _ratio(counts["mapped"], counts["included"]),
            "execution_coverage_ratio": _ratio(counts["mapped"], counts["included"]),
            "success_coverage_ratio": _ratio(counts["verified"], counts["included"]),
            "high_risk_verification_ratio": _ratio(counts["high_risk_verified"], counts["high_risk"]),
        },
        "full_product_coverage": "UNKNOWN",
        "full_product_coverage_rule": "declared-scope mapping 100% is not full-product coverage; UNKNOWN unless complete evidence exists",
        "risk_gate": {
            "blocked": bool(high_risk_blocking),
            "blocking_items": high_risk_blocking,
            "rule": "high-risk items must be PASS-verified or explicitly scoped out; otherwise the risk gate blocks COMPLETE",
        },
        "gaps": mapping["unmapped"],
        "orphan_scope_refs": mapping["orphan_scope_refs"],
        "excluded_items": [item["stable_id"] for item in excluded],
    }


def scope_manipulation_check(inventory: dict[str, Any], previous: dict[str, Any]) -> list[str]:
    """Detect scope shrinking / item deletion / high-risk re-labelling."""
    problems: list[str] = []
    prev_items = {item["stable_id"]: item for item in previous.get("items", [])}
    curr_items = {item["stable_id"]: item for item in inventory.get("items", [])}
    removed = sorted(set(prev_items) - set(curr_items))
    if removed:
        problems.append(f"SCOPE_MANIPULATION: items removed from inventory: {removed}")
    prev_included = {sid for sid, item in prev_items.items() if item["declared_scope"] == "included"}
    curr_included = {sid for sid, item in curr_items.items() if item["declared_scope"] == "included"}
    shrunk = sorted(prev_included - curr_included)
    if shrunk:
        problems.append(f"SCOPE_MANIPULATION: items moved out of declared scope: {shrunk}")
    for sid, prev in prev_items.items():
        curr = curr_items.get(sid)
        if curr is None:
            continue
        if prev.get("risk_level") in HIGH_RISK and curr.get("applicability") == "not_applicable":
            problems.append(f"SCOPE_MANIPULATION: high-risk item {sid} re-labelled not_applicable")
    prev_excluded = set(previous.get("scope", {}).get("excluded") or [])
    curr_excluded = set(inventory.get("scope", {}).get("excluded") or [])
    added_exclusions = sorted(curr_excluded - prev_excluded)
    if added_exclusions:
        problems.append(f"SCOPE_MANIPULATION: exclusion rules added: {added_exclusions}")
    return problems


def high_risk_gaps(inventory: dict[str, Any], stats: dict[str, Any]) -> list[str]:
    return list(stats.get("risk_gate", {}).get("blocking_items", []))
