"""Passive external-caller contract (T4.3): callers pass work in, engine never orchestrates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

ALLOWED_ROLES = {"owner", "reviewer", "integrator", "caller"}


def accept_call(call: dict[str, Any], root: str | Path) -> dict[str, Any]:
    problems: list[str] = []
    for field in ("caller", "task_id", "request_path"):
        if not isinstance(call.get(field), str) or not call[field]:
            problems.append(f"missing field: {field}")
    role = call.get("role", "caller")
    if role not in ALLOWED_ROLES:
        problems.append(f"invalid role: {role}")
    request_path = call.get("request_path")
    if isinstance(request_path, str):
        root_path = Path(root).resolve()
        path = (root_path / request_path).resolve()
        if root_path not in path.parents and path != root_path:
            problems.append(f"request outside root: {request_path}")
        elif not path.is_file():
            problems.append(f"request not found: {request_path}")
    return {
        "accepted": not problems,
        "problems": problems,
        "task_id": call.get("task_id"),
        "role": role,
        "orchestrates": False,
        "next": f"uiux-verify --request {request_path}" if not problems else None,
    }
