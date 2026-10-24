"""High-risk flow verification gating (TASK-05, V1.3.4).

A high-risk action may only be marked PASS when:
- it was executed in ISOLATED mode with an explicit backup/restore plan;
- the execution evidence is real (not a mock) and hash-resolvable;
- no system confirmation mechanism was bypassed (or an approved equivalent was
  recorded with its limitation).

READONLY mode can never PASS a high-risk action; it must be UNVERIFIED with a
disposition (NATIVE_INTERACTION_UNAVAILABLE or similar).
"""
from __future__ import annotations

import json
from typing import Any

ACTIONS = (
    "permanent_delete",
    "import_execute",
    "delete_confirm",
    "overwrite_save",
    "factory_reset",
    "native_file_picker",
)
MODES = ("READONLY", "ISOLATED")
REASONS = (
    "NATIVE_INTERACTION_UNAVAILABLE",
    "NOT_APPLICABLE",
    "AUDITOR_OMISSION",
    "TOOL_UNAVAILABLE",
    "ENVIRONMENT_UNAVAILABLE",
)


def validate_plan(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    seen = set()
    for item in plan.get("items", []):
        action_id = item.get("id")
        if not action_id or action_id in seen:
            problems.append(f"duplicate or missing id: {action_id}")
        seen.add(action_id)
        if item.get("action") not in ACTIONS:
            problems.append(f"{action_id}: unknown action {item.get('action')!r}")
        if item.get("mode") not in MODES:
            problems.append(f"{action_id}: invalid mode {item.get('mode')!r}")
        if item["mode"] == "ISOLATED":
            for field in ("backup_plan", "restore_plan", "target_sandbox"):
                if not item.get(field):
                    problems.append(f"{action_id}: ISOLATED mode requires {field}")
        if not item.get("evidence_requirement"):
            problems.append(f"{action_id}: evidence_requirement is required")
    return problems


def can_mark_pass(record: dict[str, Any]) -> bool:
    if record.get("mode") != "ISOLATED":
        return False
    if not record.get("executed"):
        return False
    if not record.get("evidence_refs"):
        return False
    if not record.get("backup_verified") or not record.get("restore_verified"):
        return False
    if record.get("bypassed_confirmation") and not record.get("confirmation_equivalent"):
        return False
    return True


def evaluate_plan(plan: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {record.get("id"): record for record in records}
    results = []
    for item in plan.get("items", []):
        record = by_id.get(item["id"], {})
        state = "PASS" if can_mark_pass(record) else "UNVERIFIED"
        reason = None if state == "PASS" else record.get("reason") or "NATIVE_INTERACTION_UNAVAILABLE"
        results.append({
            "id": item["id"],
            "action": item["action"],
            "mode": item["mode"],
            "state": state,
            "reason_code": reason,
            "evidence_refs": record.get("evidence_refs", []),
        })
    return {
        "schema_version": "1.3.4",
        "plan_id": plan.get("plan_id"),
        "items": results,
        "summary": {
            "total": len(results),
            "pass": len([r for r in results if r["state"] == "PASS"]),
            "unverified": len([r for r in results if r["state"] != "PASS"]),
        },
        "rule": "READONLY never passes a high-risk action; ISOLATED needs backup+restore+real evidence",
    }


def build_plan(plan_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": "1.3.4", "plan_id": plan_id, "items": items}


def load_plan(path) -> dict[str, Any]:
    import pathlib

    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
