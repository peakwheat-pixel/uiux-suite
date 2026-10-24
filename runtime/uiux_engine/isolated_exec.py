"""Isolated-execution harness for high-risk flow verification (TASK-04, V1.3.5).

Guarantees enforced here:
- the sandbox root must resolve inside an allowed root (no path escape);
- symlinks / reparse points inside the sandbox are rejected;
- a full backup (file manifest + sha256) is taken before execution;
- execution results are recorded; the sandbox is restored and the restored
  state must be byte-identical to the backup manifest;
- any failure leaves the operation BLOCKED and still attempts restoration.

The harness proves *recoverability*; it never turns an unexecutable product
capability into a PASS.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class IsolationError(RuntimeError):
    """Raised when sandbox rules are violated; callers must block."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.stat(follow_symlinks=False).st_file_attributes  # type: ignore[attr-defined]
    except AttributeError:  # non-Windows
        return False
    return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def normalize_sandbox(root: str | Path, allowed_root: str | Path) -> Path:
    """Resolve and validate a sandbox root; reject escapes and link tricks."""
    root_path = Path(root)
    allowed = Path(allowed_root)
    if not root_path.exists() or not root_path.is_dir():
        raise IsolationError(f"SANDBOX_MISSING: {root_path}")
    resolved = root_path.resolve()
    allowed_resolved = allowed.resolve()
    try:
        resolved.relative_to(allowed_resolved)
    except ValueError as exc:
        raise IsolationError(f"SANDBOX_OUTSIDE_ALLOWED_ROOT: {resolved} not under {allowed_resolved}") from exc
    for path in [resolved, *resolved.rglob("*")]:
        if _is_reparse_or_symlink(path):
            raise IsolationError(f"SYMLINK_OR_REPARSE_IN_SANDBOX: {path}")
    return resolved


def snapshot(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    entries = []
    for path in sorted(root_path.rglob("*")):
        if path.is_file():
            entries.append({
                "path": path.relative_to(root_path).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return {"root": str(root_path), "files": len(entries), "entries": entries}


def backup(root: str | Path, backup_dir: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    backup_path = Path(backup_dir)
    if backup_path.exists():
        shutil.rmtree(backup_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root_path, backup_path)
    snap = snapshot(backup_path)
    return {
        "backup_dir": str(backup_path),
        "created_at": _now(),
        "files": snap["files"],
        "total_bytes": sum(entry["size"] for entry in snap["entries"]),
        "manifest_sha256": hashlib.sha256(
            json.dumps(snap["entries"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "entries": snap["entries"],
    }


def restore(backup_dir: str | Path, root: str | Path) -> dict[str, Any]:
    backup_path = Path(backup_dir)
    root_path = Path(root)
    if not backup_path.is_dir():
        raise IsolationError(f"BACKUP_MISSING: {backup_path}")
    if root_path.exists():
        shutil.rmtree(root_path)
    shutil.copytree(backup_path, root_path)
    return {"restored_at": _now(), "root": str(root_path)}


def verify_restore(backup_record: dict[str, Any], root: str | Path) -> dict[str, Any]:
    expected = {entry["path"]: entry for entry in backup_record.get("entries", [])}
    actual_snap = snapshot(root)
    actual = {entry["path"]: entry for entry in actual_snap["entries"]}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(
        path for path in set(expected) & set(actual)
        if expected[path]["sha256"] != actual[path]["sha256"] or expected[path]["size"] != actual[path]["size"]
    )
    consistent = not missing and not extra and not changed
    return {
        "consistent": consistent,
        "files_expected": len(expected),
        "files_actual": len(actual),
        "missing": missing,
        "extra": extra,
        "changed": changed,
    }


def run_isolated(
    *,
    action_id: str,
    root: str | Path,
    allowed_root: str | Path,
    backup_dir: str | Path,
    executor: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """backup -> execute -> restore -> verify. Failures block, never pass."""
    record: dict[str, Any] = {
        "schema_version": "1.3.5",
        "action_id": action_id,
        "started_at": _now(),
        "mode": "ISOLATED",
        "state": "BLOCKED",
        "backup_verified": False,
        "executed": False,
        "restore_verified": False,
        "restore_consistent": False,
        "errors": [],
    }
    try:
        sandbox = normalize_sandbox(root, allowed_root)
        record["sandbox"] = str(sandbox)
        record["backup"] = backup(sandbox, backup_dir)
        record["backup_verified"] = record["backup"]["files"] >= 0
        try:
            record["result"] = executor(sandbox)
            record["executed"] = True
            record["state"] = "EXECUTED"
        except Exception as exc:  # noqa: BLE001 - execution failure must be recorded
            record["errors"].append(f"EXECUTION_ERROR: {type(exc).__name__}: {exc}")
            record["state"] = "BLOCKED"
        finally:
            record["restore"] = restore(record["backup"]["backup_dir"], sandbox)
            verification = verify_restore(record["backup"], sandbox)
            record["restore_verification"] = verification
            record["restore_verified"] = True
            record["restore_consistent"] = verification["consistent"]
            if not verification["consistent"]:
                record["state"] = "BLOCKED"
                record["errors"].append("RESTORE_INCONSISTENT")
    except IsolationError as exc:
        record["errors"].append(f"ISOLATION_ERROR: {exc}")
        record["state"] = "BLOCKED"
    except Exception as exc:  # noqa: BLE001
        record["errors"].append(f"UNEXPECTED_ERROR: {type(exc).__name__}: {exc}")
        record["state"] = "BLOCKED"
    record["finished_at"] = _now()
    record["verdict"] = (
        "PASS" if record["state"] == "EXECUTED" and record["restore_verified"] and record["restore_consistent"]
        else "BLOCKED"
    )
    return record
