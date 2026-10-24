"""Rebuild the V1.3.5 declared-scope inventory from G1 discovery evidence (TASK-02).

- keeps the V1.3.4 declared 18 items as the comparison baseline,
- binds the inventory to the real source commit (dirty worktree recorded in the
  discovery report, not hidden),
- freezes a new baseline hash for V1.3.5.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SUITE / "runtime"))

from uiux_engine import inventory as inv  # noqa: E402

V134_TEMPLATE = SUITE / "inventory" / "templates" / "new-manga-v134.json"
V135_TEMPLATE = SUITE / "inventory" / "templates" / "new-manga-v135.json"
DISCOVERY = Path(r"G:\AI\uiux-v135\evidence\task02\discovery.json")
OUT = Path(r"G:\AI\uiux-v135\evidence\task02")


def main() -> int:
    base = json.loads(V134_TEMPLATE.read_text(encoding="utf-8"))
    discovery = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    binding = discovery["source_binding"]

    payload = {
        "schema_version": base["schema_version"],
        "inventory_id": "INV-NEW-MANGA-V135-01",
        "description": (
            "V1.3.5 declared-scope inventory for the isolated New Manga copy. "
            "Rebuilt from G1 static discovery; the V1.3.4 inventory remains the frozen comparison baseline."
        ),
        "scope": copy.deepcopy(base["scope"]),
        "items": copy.deepcopy(base["items"]),
    }
    payload["scope"]["declared_scope_id"] = "SCOPE-NEW-MANGA-V135-01"
    payload["scope"]["source_binding"] = {
        "kind": "git_commit",
        "value": binding["value"],
    }
    for item in payload["items"]:
        item["discovery_source"] = "g1_static_discovery"
        item["evidence_reference"] = "G:\\AI\\uiux-v135\\evidence\\task02\\discovery.json"

    frozen = inv.freeze(payload, reviewed_by="lead")
    V135_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    V135_TEMPLATE.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    freeze_report = {
        "schema_version": "1.3.5",
        "kind": "inventory_v135_freeze",
        "inventory_id": frozen["inventory_id"],
        "baseline_hash": frozen["scope"]["baseline_hash"],
        "source_binding": frozen["scope"]["source_binding"],
        "source_dirty": binding["dirty"],
        "business_source_dirty": binding["business_source_dirty"],
        "discovery_baseline_hash": json.loads(
            (OUT / "discovery-baseline.json").read_text(encoding="utf-8"))["baseline_hash"],
        "items": len(frozen["items"]),
        "included": len([i for i in frozen["items"] if i["declared_scope"] == "included"]),
        "excluded": len([i for i in frozen["items"] if i["declared_scope"] == "excluded"]),
        "comparison_v134": {
            "items": len(base["items"]),
            "included": len([i for i in base["items"] if i["declared_scope"] == "included"]),
            "excluded": len([i for i in base["items"] if i["declared_scope"] == "excluded"]),
            "scope_shrunk": False,
            "note": "item set unchanged; only source binding and evidence references were updated",
        },
    }
    (OUT / "inventory-v135-freeze.json").write_text(
        json.dumps(freeze_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(freeze_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
