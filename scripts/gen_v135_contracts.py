"""Generate V1.3.5 contracts from the frozen V1.3.4 set (additive, versioned).

Rules:
- v1.3.3/v1.3.4 files are never modified.
- every v1.3.5 schema is self-contained (no cross-version ``$ref``).
- V1.3.5 coverage records gain optional evidence fields required by the
  reliability work (capability state, execution mode, backup/restore proof).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
CONTRACTS = SUITE / "contracts"
OLD, NEW = "1.3.4", "1.3.5"

# coverage-matrix v1.3.5 additive fields
COVERAGE_EXTRA_PROPERTIES = {
    "capability_available": {"type": "boolean"},
    "capability_evidence_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "execution_mode": {"type": "string", "enum": ["READONLY", "ISOLATED"]},
    "executed": {"type": "boolean"},
    "backup_verified": {"type": "boolean"},
    "restore_verified": {"type": "boolean"},
    "restore_consistent": {"type": "boolean"},
}


def main() -> int:
    generated = []
    old_files = sorted(CONTRACTS.glob(f"*.v{OLD}.schema.json"))
    if len(old_files) != 26:
        print(json.dumps({"ok": False, "error": f"expected 26 v{OLD} schemas, found {len(old_files)}"}))
        return 1
    for old in old_files:
        text = old.read_text(encoding="utf-8")
        new_text = text.replace(OLD, NEW)
        target = CONTRACTS / old.name.replace(f".v{OLD}.schema.json", f".v{NEW}.schema.json")
        payload = json.loads(new_text)
        if old.name.startswith("coverage-matrix"):
            record = payload["$defs"]["record"]
            record["properties"].update(json.loads(json.dumps(COVERAGE_EXTRA_PROPERTIES)))
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generated.append(target.name)

    enums = json.loads((CONTRACTS / f"enums.v{OLD}.json").read_text(encoding="utf-8"))
    enums["schema_version"] = NEW
    (CONTRACTS / f"enums.v{NEW}.json").write_text(
        json.dumps(enums, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generated.append(f"enums.v{NEW}.json")

    policy = json.loads((CONTRACTS / f"mode-gate-policy.v{OLD}.json").read_text(encoding="utf-8"))
    policy["schema_version"] = NEW
    (CONTRACTS / f"mode-gate-policy.v{NEW}.json").write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generated.append(f"mode-gate-policy.v{NEW}.json")

    print(json.dumps({"ok": True, "generated": len(generated), "files": generated[:3] + ["..."]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
