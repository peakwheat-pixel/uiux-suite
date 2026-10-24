"""Risk-gate semantics for V1.3.5 (TASK-01).

Replaces the vacuous high-risk PASS check with a fail-closed evaluator
that separates two questions:

  Risk Gate Integrity        — was the risk mechanism applied correctly?
  High-Risk Execution Coverage — how many declared high-risk items were really
                                executed and verified (derived, never self-reported)?

Design rules (all enforced by tests):
- Missing/empty/unknown input => BLOCKED, never PASS.
- The high-risk denominator is derived from the inventory, never from coverage.
- A PASS record needs resolvable evidence with AVAILABLE status and a hash.
- Write actions need ISOLATED mode, backup + restore proof and restore consistency.
- READONLY cannot be reported as ISOLATED; simulated cannot be reported as native.
- UNVERIFIED/PARTIAL records cannot carry a PASS marker.
- NOT_APPLICABLE requires the item to be excluded or explicitly capability-disabled.
- Declared-scope shrink is detected through the frozen inventory baseline hash.
- Reviewer disagreement blocks the gate instead of being averaged away.
- Any exception inside evaluation yields BLOCKED (no accidental PASS).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

CURRENT_VERSION = "1.3.5"
LEGACY_VERSIONS = ("1.3.4",)
WRITE_ACTIONS = {
    "permanent_delete",
    "import_execute",
    "delete_confirm",
    "overwrite_save",
    "factory_reset",
    "export_write",
}
READONLY_MODES = {"READONLY"}
ISOLATED_MODES = {"ISOLATED"}
EXECUTED_LEVELS = {"NATIVE_APP", "ISOLATED_NATIVE", "NATIVE"}
SIMULATED_LEVELS = {"SIMULATED", "SIMULATED_ONLY", "NONE"}
LEVEL_RANK = {"NONE": 0, "SIMULATED": 1, "NATIVE_APP": 2}


class RiskGateEvaluationError(RuntimeError):
    """Raised when inputs cannot be evaluated; the caller must return BLOCKED."""


def _sha256_canonical(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise RiskGateEvaluationError(f"expected list, got {type(value).__name__}")
    return value


def _norm_evidence(evidence: Any) -> dict[str, dict[str, Any]]:
    """Accept a list of items or a mapping id -> item; reject anything else."""
    if isinstance(evidence, dict):
        values = list(evidence.values())
    elif isinstance(evidence, list):
        values = evidence
    else:
        raise RiskGateEvaluationError("evidence must be a list or mapping")
    out: dict[str, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, dict):
            raise RiskGateEvaluationError("evidence item must be an object")
        item_id = item.get("id")
        if not item_id:
            raise RiskGateEvaluationError("evidence item missing id")
        out[str(item_id)] = item
    return out


def _record_scope(record: dict[str, Any]) -> str | None:
    scope = record.get("scope_ref")
    if scope:
        return str(scope)
    target = record.get("target_scope_ref")
    return str(target) if target else None


def _add(checks: list[dict[str, Any]], violations: list[str], name: str, ok: bool, detail: str) -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    if not ok:
        violations.append(f"{name}: {detail}")


def _evidence_problems(
    record: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    strict: bool,
) -> list[str]:
    problems: list[str] = []
    refs = record.get("evidence_refs") or []
    if not refs:
        return ["PASS_WITHOUT_EVIDENCE: no evidence_refs"]
    for ref in refs:
        item = evidence.get(str(ref))
        if item is None:
            problems.append(f"DANGLING_EVIDENCE: {ref}")
            continue
        status = item.get("status")
        if status != "AVAILABLE":
            problems.append(f"EVIDENCE_NOT_AVAILABLE: {ref}={status}")
        if not item.get("source_sha256"):
            problems.append(f"EVIDENCE_WITHOUT_HASH: {ref}")
        elif strict and not _is_hex64(str(item["source_sha256"])):
            problems.append(f"EVIDENCE_HASH_INVALID: {ref}")
    return problems


def _is_hex64(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


def _level_value(level: Any) -> int:
    return LEVEL_RANK.get(str(level), -1)


def _check_high_risk_pass(record: dict[str, Any], evidence: dict[str, dict[str, Any]], strict: bool) -> list[str]:
    problems: list[str] = []
    if record.get("test_state") != "PASS":
        return []
    problems.extend(_evidence_problems(record, evidence, strict))

    required = str(record.get("required_runtime_level") or "SIMULATED")
    observed = str(record.get("observed_runtime_level") or "NONE")
    if _level_value(observed) < _level_value(required) or _level_value(observed) < 0:
        problems.append(f"EVIDENCE_LEVEL_BELOW_REQUIRED: observed={observed} required={required}")

    if strict:
        mode = str(record.get("execution_mode") or "").upper()
        action = str(record.get("action") or record.get("risk_action") or "").lower()
        if mode in READONLY_MODES and action in WRITE_ACTIONS:
            problems.append(f"READONLY_CLAIMED_FOR_WRITE_ACTION: {action}")
        if action in WRITE_ACTIONS and mode != "ISOLATED":
            problems.append(f"WRITE_ACTION_NOT_ISOLATED: {action} mode={mode or 'MISSING'}")
        if mode in ISOLATED_MODES:
            if not record.get("backup_verified"):
                problems.append("ISOLATED_WITHOUT_VERIFIED_BACKUP")
            if not record.get("restore_verified"):
                problems.append("ISOLATED_WITHOUT_VERIFIED_RESTORE")
            if record.get("restore_consistent") is False:
                problems.append("RESTORE_INCONSISTENT")
        if observed in SIMULATED_LEVELS and required in EXECUTED_LEVELS:
            problems.append(f"SIMULATED_CLAIMED_NATIVE: observed={observed} required={required}")
        if record.get("simulated_only") and observed in EXECUTED_LEVELS:
            problems.append("SIMULATED_FLAG_WITH_NATIVE_LEVEL")
    return problems


def _check_not_applicable(
    record: dict[str, Any],
    inventory_ids: set[str],
    excluded_ids: set[str],
) -> list[str]:
    problems: list[str] = []
    if record.get("test_state") == "NOT_APPLICABLE" or record.get("disposition") == "NOT_APPLICABLE":
        scope = _record_scope(record)
        capability = record.get("capability_available")
        if scope not in excluded_ids and capability is not False:
            problems.append(
                f"NOT_APPLICABLE_ABUSED: scope={scope} is included and no capability_available=false evidence"
            )
        if capability is False and not record.get("capability_evidence_refs"):
            problems.append(f"NOT_APPLICABLE_WITHOUT_CAPABILITY_EVIDENCE: scope={scope}")
    return problems


def evaluate(
    inventory: dict[str, Any],
    coverage_records: Iterable[dict[str, Any]],
    evidence: Any,
    *,
    schema_version: str = CURRENT_VERSION,
    risk_plan: dict[str, Any] | None = None,
    reviewer_findings: dict[str, Any] | None = None,
    frozen_baseline_hash: str | None = None,
    evidence_hash_resolver: Any = None,
) -> dict[str, Any]:
    """Fail-closed evaluation. Returns a verdict dict; never raises for bad input."""
    try:
        return _evaluate_inner(
            inventory, coverage_records, evidence,
            schema_version=schema_version, risk_plan=risk_plan,
            reviewer_findings=reviewer_findings,
            frozen_baseline_hash=frozen_baseline_hash,
            evidence_hash_resolver=evidence_hash_resolver,
        )
    except RiskGateEvaluationError as exc:
        return _blocked(f"EVALUATION_ERROR: {exc}")
    except Exception as exc:  # noqa: BLE001 - fail closed by contract
        return _blocked(f"UNEXPECTED_EVALUATION_ERROR: {type(exc).__name__}: {exc}")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_VERSION,
        "gate_status": "BLOCKED",
        "integrity_status": "BLOCKED",
        "violations": [reason],
        "checks": [{"check": "input_integrity", "ok": False, "detail": reason}],
        "execution_coverage": {
            "scope": "inventory_declared_scope",
            "high_risk_total": 0,
            "high_risk_verified": 0,
            "high_risk_unverified": 0,
            "ratio": 0.0,
            "verified_items": [],
            "unverified_items": [],
            "source": "not_evaluated",
        },
        "a_level_risk_met": False,
        "notes": ["evaluation blocked; absence of evidence is never a pass"],
    }


def _evaluate_inner(
    inventory: dict[str, Any],
    coverage_records: Iterable[dict[str, Any]],
    evidence: Any,
    *,
    schema_version: str,
    risk_plan: dict[str, Any] | None,
    reviewer_findings: dict[str, Any] | None,
    frozen_baseline_hash: str | None,
    evidence_hash_resolver: Any,
) -> dict[str, Any]:
    if schema_version not in (CURRENT_VERSION, *LEGACY_VERSIONS):
        return _blocked(f"SCHEMA_VERSION_UNSUPPORTED: {schema_version}")
    strict = schema_version == CURRENT_VERSION
    checks: list[dict[str, Any]] = []
    violations: list[str] = []

    if not isinstance(inventory, dict):
        return _blocked("INVENTORY_NOT_OBJECT")
    items = _as_list(inventory.get("items"))
    if not items:
        return _blocked("INVENTORY_EMPTY")
    records = list(_as_list(coverage_records))
    evidence_map = _norm_evidence(evidence)
    for item in items:
        if not isinstance(item, dict) or not item.get("stable_id"):
            return _blocked("INVENTORY_ITEM_INVALID")

    included = [i for i in items if i.get("declared_scope") == "included"]
    excluded = [i for i in items if i.get("declared_scope") == "excluded"]
    if not included:
        return _blocked("NO_INCLUDED_ITEMS")
    inventory_ids = {str(i["stable_id"]) for i in items}
    excluded_ids = {str(i["stable_id"]) for i in excluded}
    high_risk = [i for i in included if str(i.get("risk_level")) in ("P0", "P1")]
    high_risk_ids = {str(i["stable_id"]) for i in high_risk}
    _add(checks, violations, "high_risk_declared", bool(high_risk),
         f"declared_high_risk={len(high_risk)} (empty set cannot pass)")

    # ---- scope integrity: frozen baseline hash / declared scope shrink
    scope_obj = inventory.get("scope") or {}
    current_baseline = scope_obj.get("baseline_hash") or inventory.get("baseline_hash")
    if frozen_baseline_hash:
        _add(checks, violations, "scope_baseline_unchanged", current_baseline == frozen_baseline_hash,
             f"current={current_baseline} frozen={frozen_baseline_hash}")

    # ---- coverage mapping
    by_scope: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            return _blocked("COVERAGE_RECORD_INVALID")
        scope = _record_scope(record)
        if not scope:
            return _blocked("COVERAGE_RECORD_WITHOUT_SCOPE")
        if scope not in inventory_ids:
            violations.append(f"UNDECLARED_SCOPE: {scope} not present in inventory")
        by_scope.setdefault(scope, []).append(record)
    missing = sorted(high_risk_ids - set(by_scope))
    _add(checks, violations, "high_risk_items_covered", not missing, f"missing={missing}")

    # ---- denominator: high-risk items declared in the plan must match inventory
    if risk_plan:
        plan_items = _as_list(risk_plan.get("items"))
        plan_ids = {str(i.get("id")) for i in plan_items if isinstance(i, dict) and i.get("id")}
        plan_high = {str(i.get("stable_id") or i.get("scope_ref")) for i in plan_items
                     if isinstance(i, dict) and str(i.get("risk_level") or "") in ("P0", "P1")}
        mismatch = sorted(plan_high - high_risk_ids) if plan_high else []
        _add(checks, violations, "risk_plan_matches_inventory", not mismatch,
             f"plan_risk_refs_not_in_inventory={mismatch}")

    # ---- per-record checks
    for record in records:
        scope = _record_scope(record) or "<unknown>"
        if record.get("test_state") == "PASS":
            for problem in _check_high_risk_pass(record, evidence_map, strict):
                violations.append(f"{scope}: {problem}")
            if evidence_hash_resolver is not None:
                for ref in record.get("evidence_refs") or []:
                    expected = evidence_map.get(str(ref), {}).get("source_sha256")
                    try:
                        actual = evidence_hash_resolver(str(ref))
                    except Exception as exc:  # noqa: BLE001
                        violations.append(f"{scope}: EVIDENCE_HASH_UNRESOLVABLE: {ref}: {exc}")
                        continue
                    if expected and actual != expected:
                        violations.append(f"{scope}: EVIDENCE_HASH_MISMATCH: {ref}")
                    elif expected is None:
                        violations.append(f"{scope}: EVIDENCE_WITHOUT_HASH: {ref}")
        elif record.get("test_state") in ("UNVERIFIED", "PARTIAL", "BLOCKED", "FAIL"):
            disposition = record.get("disposition")
            if not disposition and strict:
                violations.append(f"{scope}: UNVERIFIED_WITHOUT_DISPOSITION")
            if record.get("pass_marker") is True or record.get("verified") is True:
                violations.append(f"{scope}: UNVERIFIED_MARKED_AS_PASS")
        for problem in _check_not_applicable(record, inventory_ids, excluded_ids):
            violations.append(f"{scope}: {problem}")

    # ---- known failure classes that must never be silently accepted
    if any(r.get("test_state") == "PASS" and r.get("execution_mode") == "READONLY"
           and str(r.get("action") or "").lower() in WRITE_ACTIONS for r in records):
        violations.append("READONLY_PASS_FOR_WRITE_ACTION")

    # ---- reviewer conflict blocks the gate
    if reviewer_findings:
        conflicts = reviewer_findings.get("conflicts") or []
        if conflicts:
            violations.append(f"REVIEWER_CONFLICT: {len(conflicts)} conflicting finding(s)")
            checks.append({"check": "reviewer_conflict", "ok": False,
                           "detail": f"conflicts={len(conflicts)}"})

    integrity_status = "PASS" if not violations else "FAIL"

    # ---- execution coverage (derived, not self-reported)
    verified_items: list[str] = []
    unverified_items: list[dict[str, str]] = []
    for item in high_risk:
        stable_id = str(item["stable_id"])
        item_records = by_scope.get(stable_id, [])
        verified = False
        for record in item_records:
            if record.get("test_state") != "PASS":
                continue
            problems = _check_high_risk_pass(record, evidence_map, strict)
            if not problems:
                verified = True
                break
        if verified:
            verified_items.append(stable_id)
        else:
            reason = "UNVERIFIED"
            for record in item_records:
                if record.get("test_state") != "PASS" and record.get("disposition"):
                    reason = str(record["disposition"])
                    break
            unverified_items.append({"stable_id": stable_id, "risk_level": str(item.get("risk_level")), "reason": reason})
    total = len(high_risk)
    ratio = round(len(verified_items) / total, 4) if total else 0.0
    coverage = {
        "scope": "inventory_declared_scope",
        "high_risk_total": total,
        "high_risk_verified": len(verified_items),
        "high_risk_unverified": total - len(verified_items),
        "ratio": ratio,
        "verified_items": verified_items,
        "unverified_items": unverified_items,
        "source": "derived_from_inventory_and_coverage",
    }

    gate_status = "PASS" if integrity_status == "PASS" else "FAIL"
    a_level_met = gate_status == "PASS" and coverage["high_risk_unverified"] == 0
    return {
        "schema_version": CURRENT_VERSION,
        "evaluated_version": schema_version,
        "strict": strict,
        "gate_status": gate_status,
        "integrity_status": integrity_status,
        "violations": violations,
        "checks": checks,
        "execution_coverage": coverage,
        "a_level_risk_met": a_level_met,
        "notes": [
            "integrity PASS means the risk mechanism was applied correctly; it does not mean high-risk execution is complete",
            "execution coverage is derived from the inventory denominator, never from a self-reported ratio",
        ],
    }


def digest(verdict: dict[str, Any]) -> str:
    return _sha256_canonical(verdict)
