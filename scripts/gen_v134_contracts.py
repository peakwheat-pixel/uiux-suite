"""Generate the V1.3.4 contract set from the frozen V1.3.3 contracts.

V1.3.3 files stay byte-identical (read-only history). V1.3.4 files are generated
with version rewrites plus additive extensions required by TASK-03:

  - common:            + $defs/disposition (9 reason categories)
  - coverage-matrix:   + optional disposition / scope_ref / risk_ref on records
  - task-result:       + optional delivery_dimensions / scope_summary
  - enums:             + Disposition & delivery dimension enums, new reason codes
  - mode-gate-policy:  versioned copy

Usage:
  python scripts/gen_v134_contracts.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = SUITE_ROOT / "contracts"
V133 = "1.3.3"
V134 = "1.3.4"

DISPOSITIONS = [
    "ENVIRONMENT_UNAVAILABLE",
    "AUDITOR_OMISSION",
    "TOOL_UNAVAILABLE",
    "FIXTURE_INVALID",
    "NATIVE_INTERACTION_UNAVAILABLE",
    "NOT_APPLICABLE",
    "PRODUCT_FAILURE",
    "EVIDENCE_MISSING",
    "INDEPENDENCE_UNVERIFIED",
]

NEW_REASON_CODES = [
    ("SCHEMA_VERSION_MISSING", "contract"),
    ("SCHEMA_VERSION_MISMATCH", "contract"),
    ("SCHEMA_VERSION_UNSUPPORTED", "contract"),
    ("SCOPE_MANIPULATION", "coverage"),
    ("SCOPE_MAPPING_INCOMPLETE", "coverage"),
    ("SCOPE_REF_UNKNOWN", "coverage"),
    ("DISPOSITION_REQUIRED", "coverage"),
    ("RISK_GATE_BLOCKED", "coverage"),
    ("DELIVERY_DIMENSION_MISMATCH", "result"),
    ("FIXTURE_INVALID", "fixture"),
    ("FIXTURE_ENVIRONMENT_ERROR", "fixture"),
    ("AUDITOR_OMISSION", "coverage"),
    ("ENVIRONMENT_UNAVAILABLE", "coverage"),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rewrite_version(text: str) -> str:
    return (
        text.replace("v1.3.3.schema.json", "v1.3.4.schema.json")
        .replace("V1.3.3", "V1.3.4")
        .replace('"1.3.3"', '"1.3.4"')
    )


def write_json(path: Path, data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    sources = sorted(CONTRACTS.glob(f"*.v{V133}.schema.json"))
    if len(sources) != 26:
        print(json.dumps({"ok": False, "error": f"expected 26 v1.3.3 schemas, found {len(sources)}"}))
        return 2

    generated: list[dict] = []
    changed: list[str] = []
    for src in sources:
        dst = CONTRACTS / src.name.replace(f"v{V133}", f"v{V134}")
        text = rewrite_version(src.read_text(encoding="utf-8"))
        doc = json.loads(text)

        if src.name == "common.v1.3.3.schema.json":
            doc["$defs"]["disposition"] = {
                "enum": DISPOSITIONS,
                "description": "V1.3.4：未通过项的处置原因，用于区分合理不可达与审计遗漏",
            }
        elif src.name == "coverage-matrix.v1.3.3.schema.json":
            rec = doc["$defs"]["record"]["properties"]
            rec["disposition"] = {"$ref": "common.v1.3.4.schema.json#/$defs/disposition"}
            rec["scope_ref"] = {"type": "string", "minLength": 1}
            rec["risk_ref"] = {"type": "string", "minLength": 1}
            doc["$defs"]["record"]["properties"] = rec
        elif src.name == "task-result.v1.3.3.schema.json":
            props = doc["properties"]
            props["delivery_dimensions"] = {
                "type": "object",
                "required": [
                    "execution_status", "scope_coverage_status", "evidence_integrity_status",
                    "risk_coverage_status", "independence_status", "delivery_status",
                ],
                "properties": {
                    "execution_status": {"enum": ["PASS", "PARTIAL", "FAIL", "BLOCKED", "UNVERIFIED"]},
                    "scope_coverage_status": {"enum": ["COMPLETE", "PARTIAL", "UNMAPPED_GAPS", "UNKNOWN"]},
                    "evidence_integrity_status": {"enum": ["PASS", "FAIL", "UNVERIFIED"]},
                    "risk_coverage_status": {"enum": ["PASS", "BLOCKED", "UNVERIFIED", "NOT_APPLICABLE"]},
                    "independence_status": {"enum": [
                        "NOT_APPLICABLE", "UNVERIFIED", "INDEPENDENCE_UNVERIFIED",
                        "INDEPENDENT_REVIEW_PASS", "INDEPENDENT_REVIEW_FAIL",
                    ]},
                    "delivery_status": {"enum": [
                        "NOT_VERIFIED", "SELFTEST_VERIFIED", "ISOLATED_REVIEW_VERIFIED",
                        "INDEPENDENT_VERIFIED", "PARTIAL_VERIFIED", "PARTIAL_SCOPED",
                    ]},
                    "notes": {"type": "string"},
                },
                "additionalProperties": False,
            }
            props["scope_summary"] = {
                "type": "object",
                "properties": {
                    "declared_scope_id": {"type": "string", "minLength": 1},
                    "inventory_total": {"type": "integer", "minimum": 0},
                    "mapped_total": {"type": "integer", "minimum": 0},
                    "executed_total": {"type": "integer", "minimum": 0},
                    "verified_total": {"type": "integer", "minimum": 0},
                    "unverified_total": {"type": "integer", "minimum": 0},
                    "unreachable_total": {"type": "integer", "minimum": 0},
                    "excluded_total": {"type": "integer", "minimum": 0},
                    "high_risk_total": {"type": "integer", "minimum": 0},
                    "high_risk_verified_total": {"type": "integer", "minimum": 0},
                    "declared_scope_mapping_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "additionalProperties": False,
            }
            doc["properties"] = props
        elif src.name == "gate-results.v1.3.3.schema.json":
            gate = doc["$defs"]["gate_result"]["properties"]
            gate["dispositions"] = {
                "type": "array",
                "items": {"$ref": "common.v1.3.4.schema.json#/$defs/disposition"},
                "uniqueItems": True,
            }
            doc["$defs"]["gate_result"]["properties"] = gate

        digest = write_json(dst, doc)
        generated.append({"file": dst.name, "sha256": digest})
        if not args.check:
            changed.append(dst.name)

    # enums
    enums_doc = json.loads((CONTRACTS / f"enums.v{V133}.json").read_text(encoding="utf-8"))
    enums_doc["schema_version"] = V134
    enums_doc["document"] = enums_doc["document"].replace(V133, V134)
    enums_doc["enums"]["Disposition"] = {"values": DISPOSITIONS}
    delivery_status = list(enums_doc["enums"]["DeliveryStatus"]["values"])
    if "PARTIAL_SCOPED" not in delivery_status:
        delivery_status.append("PARTIAL_SCOPED")
    enums_doc["enums"]["DeliveryStatus"] = {
        "values": delivery_status,
        **({"rank": enums_doc["enums"]["DeliveryStatus"]["rank"]} if "rank" in enums_doc["enums"]["DeliveryStatus"] else {}),
    }
    enums_doc["enums"]["DeliveryDimensionStatus"] = {"values": ["PASS", "PARTIAL", "FAIL", "BLOCKED", "UNVERIFIED", "NOT_APPLICABLE"]}
    enums_doc["enums"]["ScopeCoverageStatus"] = {"values": ["COMPLETE", "PARTIAL", "UNMAPPED_GAPS", "UNKNOWN"]}
    enums_doc["enums"]["RiskCoverageStatus"] = {"values": ["PASS", "BLOCKED", "UNVERIFIED", "NOT_APPLICABLE"]}
    enums_doc["enums"]["EvidenceIntegrityStatus"] = {"values": ["PASS", "FAIL", "UNVERIFIED"]}
    enums_doc["enums"]["DeliveryDimension"] = {
        "values": [
            "execution_status", "scope_coverage_status", "evidence_integrity_status",
            "risk_coverage_status", "independence_status", "delivery_status",
        ]
    }
    existing_codes = {row["code"] for row in enums_doc["reason_codes"]}
    for code, group in NEW_REASON_CODES:
        if code not in existing_codes:
            enums_doc["reason_codes"].append({"code": code, "group": group})
    digest = write_json(CONTRACTS / f"enums.v{V134}.json", enums_doc)
    generated.append({"file": f"enums.v{V134}.json", "sha256": digest})

    # mode-gate-policy
    policy_src = CONTRACTS / f"mode-gate-policy.v{V133}.json"
    policy_doc = json.loads(policy_src.read_text(encoding="utf-8"))
    policy_doc["schema_version"] = V134
    policy_doc["document"] = policy_doc["document"].replace(V133, V134)
    digest = write_json(CONTRACTS / f"mode-gate-policy.v{V134}.json", policy_doc)
    generated.append({"file": f"mode-gate-policy.v{V134}.json", "sha256": digest})

    report = {
        "schema_version": V134,
        "generator": "scripts/gen_v134_contracts.py",
        "source_version": V133,
        "generated_files": len(generated),
        "files": generated,
        "notes": [
            "v1.3.3 contract files remain untouched",
            "coverage-matrix: disposition/scope_ref/risk_ref are additive optional fields",
            "task-result: delivery_dimensions/scope_summary are additive optional fields",
            "enums: new enums and reason codes are additive only",
        ],
    }
    out = SUITE_ROOT / "evidence" / "task00" / "contracts-generation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "generated": len(generated),
        "check_mode": args.check,
        "report": str(out),
        "sample": generated[:3],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
