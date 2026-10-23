"""Byte-level evidence vault verification and quarantine (T3.5)."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import contracts, snapshot

AVAILABLE = "AVAILABLE"


def _refs(item: dict[str, Any]) -> list[str]:
    return [ref for ref in item.get("references", []) if isinstance(ref, str)]


def verify(manifest: dict[str, Any], root: str | Path, *, quarantine_dir: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    problems = contracts.validation_errors("evidence-manifest", manifest)
    report = {"ok": not problems, "problems": problems, "verified": [], "invalid": [], "missing": [], "quarantined": []}
    if problems:
        return report
    quarantine = Path(quarantine_dir) if quarantine_dir else None
    for item in manifest["items"]:
        if item.get("status") != AVAILABLE:
            continue
        expected = {item["source_sha256"]} if item.get("source_sha256") else set()
        if not expected:
            report["missing"].append({"id": item["id"], "reason": "AVAILABLE item has no source_sha256"})
            continue
        refs = _refs(item)
        if not refs:
            report["missing"].append({"id": item["id"], "reason": "no references"})
            continue
        found = False
        for ref in refs:
            path = (root_path / ref).resolve()
            if root_path not in path.parents and path != root_path:
                report["invalid"].append({"id": item["id"], "ref": ref, "reason": "outside root"})
                continue
            if not path.is_file():
                continue
            found = True
            digest = snapshot.sha256_file(path)
            if expected and digest not in expected:
                report["invalid"].append({"id": item["id"], "ref": ref, "expected": sorted(expected), "actual": digest})
                if quarantine:
                    target = quarantine / item["id"] / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    report["quarantined"].append(str(target))
            else:
                report["verified"].append({"id": item["id"], "ref": ref, "sha256": digest})
        if not found and not any(entry["id"] == item["id"] for entry in report["invalid"]):
            report["missing"].append({"id": item["id"], "reason": "referenced file missing"})
    report["ok"] = not problems and not report["invalid"] and not report["missing"]
    return report
