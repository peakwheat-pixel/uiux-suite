"""CLI for the V1.3.5 risk gate (TASK-01 integration).

Usage:
  python scripts/v135_risk_gate.py --inventory <json> --coverage <json> \
      --evidence <json> --schema-version 1.3.4 --out <json>

Exit code: 0 PASS, 10 FAIL, 11 BLOCKED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE / "runtime"))

from uiux_engine import risk_gate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--schema-version", default="1.3.5")
    parser.add_argument("--frozen-baseline-hash")
    parser.add_argument("--reviewer-findings")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    coverage = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    reviewer = json.loads(Path(args.reviewer_findings).read_text(encoding="utf-8")) if args.reviewer_findings else None
    verdict = risk_gate.evaluate(
        inventory,
        coverage.get("records", coverage),
        evidence.get("items", evidence),
        schema_version=args.schema_version,
        reviewer_findings=reviewer,
        frozen_baseline_hash=args.frozen_baseline_hash,
    )
    verdict["verdict_digest"] = risk_gate.digest(verdict)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate_status": verdict["gate_status"],
        "integrity_status": verdict["integrity_status"],
        "execution_coverage": verdict["execution_coverage"],
        "a_level_risk_met": verdict["a_level_risk_met"],
        "violations": verdict["violations"],
        "out": args.out,
    }, ensure_ascii=False, indent=2))
    return {"PASS": 0, "FAIL": 10, "BLOCKED": 11}.get(verdict["gate_status"], 11)


if __name__ == "__main__":
    raise SystemExit(main())
