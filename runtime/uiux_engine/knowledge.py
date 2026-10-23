"""Knowledge index loading and integrity verification (T2.4/M11)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import contracts

INDEX_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "index.v1.0.json"


def load_index(path: str | Path | None = None) -> dict[str, Any]:
    return contracts.load_json(path or INDEX_PATH)


def verify(index: dict[str, Any] | None = None, root: str | Path | None = None) -> dict[str, Any]:
    index = index or load_index()
    root_path = Path(root) if root else Path(__file__).resolve().parents[2]
    problems = list(contracts.validation_errors("knowledge-index", index))
    verified: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    if problems:
        return {"ok": False, "problems": problems, "verified": verified, "skipped": skipped}
    seen: set[str] = set()
    for entry in index["entries"]:
        if entry["id"] in seen:
            problems.append(f"duplicate knowledge id: {entry['id']}")
        seen.add(entry["id"])
        path = entry.get("path")
        checksum = entry.get("checksum")
        if not path:
            skipped.append({"id": entry["id"], "reason": "reference-only entry"})
            continue
        target = (root_path / path).resolve()
        if not target.is_file():
            problems.append(f"{entry['id']}: missing file {path}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if checksum and actual != checksum:
            problems.append(f"{entry['id']}: checksum mismatch")
            continue
        if not checksum:
            problems.append(f"{entry['id']}: bundled entry has no checksum")
            continue
        verified.append({"id": entry["id"], "path": path, "sha256": actual})
    return {"ok": not problems, "problems": problems, "verified": verified, "skipped": skipped}
