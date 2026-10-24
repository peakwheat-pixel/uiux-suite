"""G1 discovery CLI for V1.3.5 TASK-02.

Usage:
  python scripts/v135_discovery.py --source <root> --inventory <json> --out-dir <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE / "runtime"))

from uiux_engine import discovery  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    discovery_report = discovery.discover_g1(Path(args.source))
    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    reconciliation = discovery.reconcile_inventory(discovery_report, inventory)
    baseline = {
        "schema_version": "1.3.5",
        "kind": "g1_discovery_baseline",
        "baseline_hash": discovery.freeze_discovery(discovery_report),
        "source_binding": discovery_report["source_binding"],
        "scanned": discovery_report["scanned"],
        "inventory_reconciliation_digest": discovery.freeze_discovery(reconciliation),
    }
    (out / "discovery.json").write_text(json.dumps(discovery_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "inventory-reconciliation.json").write_text(json.dumps(reconciliation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "discovery-baseline.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "baseline_hash": baseline["baseline_hash"],
        "source_binding": baseline["source_binding"],
        "summary": discovery_report["summary"],
        "reconciliation": {key: reconciliation[key] for key in ("found", "not_found", "excluded_declared")},
        "not_found_items": [row["stable_id"] for row in reconciliation["items"] if row["state"] == "NOT_FOUND_IN_SOURCE"],
        "out_dir": str(out),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
