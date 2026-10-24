"""Runtime-to-source binding (TASK-06, V1.3.4).

Three trust levels, strongest first:
  build_provenance  — a signed build manifest lists the runtime artifact hash;
  artifact_hash     — the runtime artifact hash is bound to a frozen source id;
  runtime_marker    — only the runtime artifact hash is known.

Rules:
- Never claim a higher level than the evidence supports.
- `verify_binding` recomputes every hash; mismatch fails closed.
- A dirty source tree is recorded, and `build_provenance` is refused for dirty
  trees because a manifest could not certify uncommitted content.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEVELS = ("NONE", "runtime_marker", "artifact_hash", "build_provenance")
LEVEL_RANK = {level: index for index, level in enumerate(LEVELS)}
SOURCE_DIRS = ("apps/desktop/frontend/src", "apps/desktop/src-tauri/src", "apps/desktop/src-tauri/tauri.conf.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(source_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(source_root), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return proc.stdout.strip()


def source_fingerprint(source_root: Path) -> dict[str, Any]:
    head = git(source_root, "rev-parse", "HEAD")
    dirty = bool(git(source_root, "status", "--porcelain"))
    dirs: dict[str, str] = {}
    for relative in SOURCE_DIRS:
        path = source_root / relative
        if path.is_file():
            dirs[relative] = sha256_file(path)
        elif path.is_dir():
            digest = hashlib.sha256()
            for item in sorted(path.rglob("*")):
                if item.is_file():
                    digest.update(item.relative_to(source_root).as_posix().encode("utf-8"))
                    digest.update(b"\x00")
                    digest.update(bytes.fromhex(sha256_file(item)))
            dirs[relative] = digest.hexdigest()
    aggregate = hashlib.sha256()
    for key in sorted(dirs):
        aggregate.update(key.encode("utf-8"))
        aggregate.update(b"\x00")
        aggregate.update(bytes.fromhex(dirs[key]))
    return {
        "kind": "git_commit",
        "value": head or "unknown",
        "dirty": dirty,
        "tree_digest": aggregate.hexdigest(),
        "components": dirs,
    }


def bind_runtime(
    runtime_exe: Path,
    source_root: Path,
    build_manifest: Path | None = None,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    source = source_fingerprint(source_root)
    runtime = {
        "path": str(runtime_exe),
        "sha256": sha256_file(runtime_exe) if runtime_exe.is_file() else None,
        "size": runtime_exe.stat().st_size if runtime_exe.is_file() else None,
    }
    level = "NONE"
    checks = []

    if build_manifest and build_manifest.is_file():
        manifest = json.loads(build_manifest.read_text(encoding="utf-8"))
        entries = manifest.get("files") or manifest.get("release_manifest", {}).get("files") or []
        match = next(
            (entry for entry in entries if str(entry.get("path", "")).endswith(runtime_exe.name) and entry.get("sha256") == runtime["sha256"]),
            None,
        )
        checks.append({
            "check": "build_manifest_artifact",
            "ok": match is not None,
            "detail": f"manifest={build_manifest.name} matched={bool(match)}",
        })
        if match is not None and not source["dirty"]:
            level = "build_provenance"
        elif match is not None:
            checks.append({"check": "build_manifest_dirty_source", "ok": False,
                           "detail": "source tree is dirty; build_provenance cannot certify uncommitted content"})
    if level != "build_provenance" and runtime["sha256"] and source["value"] != "unknown":
        level = "artifact_hash"
        checks.append({"check": "artifact_hash_bound_to_source", "ok": True,
                       "detail": f"runtime={runtime['sha256'][:12]} source={source['value'][:12]}"})
    elif level != "build_provenance":
        level = "runtime_marker"
        checks.append({"check": "runtime_marker_only", "ok": True,
                       "detail": "no source id available; only the runtime hash is bound"})

    return {
        "schema_version": "1.3.4",
        "binding_id": f"BIND-{runtime['sha256'][:12] if runtime['sha256'] else 'UNKNOWN'}",
        "level": level,
        "runtime": runtime,
        "source": source,
        "checks": checks,
        "created_at": now or datetime.now(timezone.utc).isoformat(),
        "rule": "declared level never exceeds the evidence; dirty sources cannot claim build_provenance",
    }


def verify_binding(binding: dict[str, Any], runtime_exe: Path, source_root: Path) -> list[str]:
    problems: list[str] = []
    if not runtime_exe.is_file():
        problems.append("RUNTIME_MISSING")
        return problems
    actual = sha256_file(runtime_exe)
    if actual != binding.get("runtime", {}).get("sha256"):
        problems.append(f"RUNTIME_HASH_MISMATCH: {actual} != {binding.get('runtime', {}).get('sha256')}")
    source = source_fingerprint(source_root)
    if source["value"] != binding.get("source", {}).get("value"):
        problems.append("SOURCE_ID_MISMATCH")
    if source["tree_digest"] != binding.get("source", {}).get("tree_digest"):
        problems.append("SOURCE_TREE_MISMATCH")
    if binding.get("level") not in LEVELS:
        problems.append(f"BINDING_LEVEL_INVALID: {binding.get('level')!r}")
    return problems


def level_at_least(binding: dict[str, Any], required: str) -> bool:
    level = binding.get("level", "NONE")
    if level not in LEVEL_RANK or required not in LEVEL_RANK:
        return False
    return LEVEL_RANK[level] >= LEVEL_RANK[required]
