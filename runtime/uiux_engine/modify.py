"""Controlled change plan application with write-scope enforcement and revert (T3.1)."""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import contracts, snapshot

SAFE_PATH = Path


def _sha256_file(path: Path) -> str:
    return snapshot.sha256_file(path)


def _safe_relative(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe path: {path}")
    return candidate


def _within(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == root.resolve() or root.resolve() in resolved.parents for root in roots)


def validate_plan(plan: dict[str, Any], root: str | Path) -> list[str]:
    problems = list(contracts.validation_errors("change-plan", plan))
    if problems:
        return problems
    root_path = Path(root).resolve()
    scope = [(root_path / _safe_relative(item)).resolve() for item in plan["write_scope"]]
    seen: set[str] = set()
    for change in plan["changes"]:
        rel = _safe_relative(change["path"])
        target = (root_path / rel).resolve()
        if change["path"] in seen:
            problems.append(f"duplicate change path: {change['path']}")
        seen.add(change["path"])
        if not _within(target, scope):
            problems.append(f"outside write scope: {change['path']}")
        action = change["action"]
        exists = target.is_file()
        if action == "create" and exists:
            problems.append(f"create target already exists: {change['path']}")
        if action in ("modify", "delete"):
            if not exists:
                problems.append(f"target missing for {action}: {change['path']}")
            elif change.get("sha256_before") != _sha256_file(target):
                problems.append(f"before hash mismatch: {change['path']}")
        if action in ("create", "modify") and "content" not in change:
            problems.append(f"missing content for {action}: {change['path']}")
    return problems


def apply_plan(plan: dict[str, Any], root: str | Path, *, backup_dir: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    problems = validate_plan(plan, root_path)
    if problems:
        return {"ok": False, "applied": [], "problems": problems, "backup": None}
    scope = [(root_path / _safe_relative(item)).resolve() for item in plan["write_scope"]]
    for item in scope:
        item.mkdir(parents=True, exist_ok=True)
    backup = Path(backup_dir) if backup_dir else Path(tempfile.mkdtemp(prefix="uiux-change-backup-"))
    backup.mkdir(parents=True, exist_ok=True)
    applied = []
    for change in plan["changes"]:
        target = (root_path / _safe_relative(change["path"])).resolve()
        backup_target = backup / _safe_relative(change["path"])
        backup_target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            shutil.copy2(target, backup_target)
        if change["action"] == "delete":
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change["content"], encoding="utf-8")
        applied.append({"path": change["path"], "action": change["action"]})
    return {
        "ok": True,
        "applied": applied,
        "problems": [],
        "backup": str(backup),
        "scope": [str(item.relative_to(root_path)) for item in scope],
    }


def revert_plan(plan: dict[str, Any], root: str | Path, backup_dir: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    backup = Path(backup_dir).resolve()
    restored = []
    for change in plan["changes"]:
        rel = _safe_relative(change["path"])
        target = (root_path / rel).resolve()
        backup_target = backup / rel
        if backup_target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_target, target)
            restored.append({"path": change["path"], "action": "restored"})
        elif change["action"] == "create":
            target.unlink(missing_ok=True)
            restored.append({"path": change["path"], "action": "removed-created"})
        else:
            restored.append({"path": change["path"], "action": "missing-backup"})
    return {"ok": True, "restored": restored}


def diff_plan(plan: dict[str, Any], root: str | Path) -> list[dict[str, Any]]:
    root_path = Path(root).resolve()
    result = []
    for change in plan["changes"]:
        target = root_path / _safe_relative(change["path"])
        before = _sha256_file(target) if target.is_file() else None
        after = None
        if change.get("content") is not None:
            import hashlib

            after = hashlib.sha256(change["content"].encode("utf-8")).hexdigest()
        result.append({"path": change["path"], "action": change["action"], "before": before, "after": after})
    return result
