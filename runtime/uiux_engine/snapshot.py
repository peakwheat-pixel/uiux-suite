"""Non-Git directory snapshots for rollback evidence (M17).

A snapshot is a JSON document with relative POSIX paths and SHA-256 digests.
It is intentionally simple: no timestamps inside the digest, deterministic
ordering, and no content copies unless `backup_tree` is explicitly requested.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_IGNORE = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}
SNAPSHOT_KIND = "uiux-dir-snapshot"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path, ignore: Iterable[str] = DEFAULT_IGNORE) -> list[Path]:
    ignored = set(ignore)
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in ignored for part in relative_parts):
            continue
        files.append(path)
    return files


def dir_digest(root: str | Path, ignore: Iterable[str] = DEFAULT_IGNORE) -> dict[str, str]:
    base = Path(root).resolve()
    if not base.is_dir():
        raise FileNotFoundError(base)
    return {
        path.relative_to(base).as_posix(): sha256_file(path)
        for path in iter_files(base, ignore)
    }


def build_snapshot(root: str | Path, ignore: Iterable[str] = DEFAULT_IGNORE) -> dict:
    files = dir_digest(root, ignore)
    return {
        "kind": SNAPSHOT_KIND,
        "schema_version": "1.3.3",
        "root_name": Path(root).name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "files": files,
    }


def write_snapshot(root: str | Path, out: str | Path) -> dict:
    snapshot = build_snapshot(root)
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def load_snapshot(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("kind") != SNAPSHOT_KIND or not isinstance(data.get("files"), dict):
        raise ValueError(f"not a uiux dir snapshot: {path}")
    return data


def diff_snapshots(before: dict, after: dict) -> dict:
    first = before["files"]
    second = after["files"]
    added = sorted(set(second) - set(first))
    removed = sorted(set(first) - set(second))
    changed = sorted(path for path in set(first) & set(second) if first[path] != second[path])
    return {"added": added, "removed": removed, "changed": changed, "identical": not (added or removed or changed)}


def backup_tree(root: str | Path, destination: str | Path, ignore: Iterable[str] = DEFAULT_IGNORE) -> Path:
    source = Path(root).resolve()
    target = Path(destination)
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    ignored = set(ignore)
    for path in iter_files(source, ignore):
        relative = path.relative_to(source)
        if any(part in ignored for part in relative.parts):
            continue
        destination_path = target / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination_path)
    return target
