"""Risk classification and safety metrics (T3.7)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

P0 = "P0_READ_ONLY"
P1 = "P1_ADDITIVE"
P2 = "P2_MODIFY"
P3 = "P3_DESTRUCTIVE_OR_USER_DATA"


def classify_plan(plan: dict[str, Any]) -> dict[str, Any]:
    level = P1
    reasons: list[str] = []
    for change in plan.get("changes", []):
        action = change.get("action")
        if action == "delete":
            level = P3
            reasons.append(f"delete: {change['path']}")
        elif action == "modify":
            if level != P3:
                level = P2
            reasons.append(f"modify: {change['path']}")
        elif action == "create":
            reasons.append(f"create: {change['path']}")
    if not plan.get("changes"):
        level = P0
        reasons.append("no changes")
    return {
        "level": level,
        "reasons": reasons,
        "requires_confirmation": level == P3,
        "allowed_without_user": level in (P0, P1, P2),
    }


def metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    real_user_data_writes = sum(int(run.get("real_user_data_writes", 0)) for run in runs)
    protected_writes = sum(int(run.get("protected_root_writes", 0)) for run in runs)
    blocked = sum(int(run.get("blocked_actions", 0)) for run in runs)
    p3 = sum(1 for run in runs for action in run.get("actions", []) if action.get("level") == P3)
    return {
        "runs": len(runs),
        "real_user_data_writes": real_user_data_writes,
        "protected_root_writes": protected_writes,
        "blocked_actions": blocked,
        "p3_actions": p3,
        "zero_real_user_data_writes": real_user_data_writes == 0,
        "zero_protected_root_writes": protected_writes == 0,
    }


def audit_write_targets(root: str | Path, targets: list[str]) -> list[str]:
    root_path = Path(root).resolve()
    problems: list[str] = []
    for target in targets:
        path = (root_path / target).resolve()
        if path != root_path and root_path not in path.parents:
            problems.append(f"outside project root: {target}")
    return problems
