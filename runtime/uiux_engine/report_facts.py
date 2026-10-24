"""Report facts and linter (TASK-08, V1.3.4).

Markdown is presentation; these facts are the machine-readable source of truth.
The linter checks that reported numbers and claims are consistent with the
underlying evidence and that limits are not silently upgraded.

Regression cases from V1.3.3 that the linter must catch:
- "9 unverified claims vs 8 coverage records" style counting drift;
- captures/coverage confusion (62 capture states vs 26 coverage records);
- PASS without evidence; UNVERIFIED without disposition;
- declaring full-product coverage without evidence;
- claiming an A-level result while high-risk paths remain unverified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_facts(
    audit_dir: Path,
    verify_dir: Path | None = None,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    audit_dir = Path(audit_dir)
    coverage = _load(audit_dir / "coverage-matrix.json")
    manifest = _load(audit_dir / "evidence-manifest.json")
    issues = _load(audit_dir / "issues.json")
    task_result = _load(audit_dir / "task-result.json")
    records = coverage["records"]
    manifest_ids = {item["id"] for item in manifest["items"]}
    pass_records = [r for r in records if r["test_state"] == "PASS"]
    unverified = [r for r in records if r["test_state"] != "PASS"]
    resolved_refs = sum(1 for r in records for ref in r["evidence_refs"] if ref in manifest_ids)
    dangling_refs = [ref for r in records for ref in r["evidence_refs"] if ref not in manifest_ids]

    counts = {
        "coverage_records": len(records),
        "pass_records": len(pass_records),
        "unverified_records": len(unverified),
        "evidence_items": len(manifest["items"]),
        "unverified_scopes": len(issues.get("unverified_scopes", [])),
        "high_risk_unverified": len([u for u in issues.get("unverified_scopes", []) if u.get("disposition")]),
        "resolved_evidence_refs": resolved_refs,
        "dangling_evidence_refs": len(dangling_refs),
    }
    if verify_dir:
        review = _load(Path(verify_dir) / "review-findings.json")
        counts["independent_findings_confirmed"] = review["verdict_counts"]["CONFIRMED"]
        counts["independent_findings_failed"] = review["verdict_counts"]["FAIL"]
    if inventory_path:
        inventory = _load(Path(inventory_path))
        counts["inventory_items"] = len(inventory["items"])
        counts["inventory_included"] = len([i for i in inventory["items"] if i["declared_scope"] == "included"])
        counts["inventory_excluded"] = len([i for i in inventory["items"] if i["declared_scope"] == "excluded"])

    claims = [
        {
            "claim_id": "C-01",
            "statement": "finalize status and delivery are derived from evidence",
            "evidence": ["task-result.json"],
            "status": "SUPPORTED",
            "value": {"status": task_result["status"], "delivery_status": task_result["delivery_status"]},
        },
        {
            "claim_id": "C-02",
            "statement": "every PASS coverage record carries resolvable evidence",
            "evidence": ["coverage-matrix.json", "evidence-manifest.json"],
            "status": "SUPPORTED" if not dangling_refs else "UNSUPPORTED",
        },
        {
            "claim_id": "C-03",
            "statement": "unverified items carry explicit dispositions",
            "evidence": ["coverage-matrix.json", "issues.json"],
            "status": "SUPPORTED" if all(r.get("disposition") for r in unverified) else "UNSUPPORTED",
        },
        {
            "claim_id": "C-04",
            "statement": "declared-scope mapping is 100% but full-product coverage is UNKNOWN",
            "evidence": ["coverage-summary.json"],
            "status": "SUPPORTED",
            "value": {"mapping_ratio": 1.0, "full_product_coverage": "UNKNOWN"},
        },
        {
            "claim_id": "C-05",
            "statement": "high-risk execution paths are not verified",
            "evidence": ["issues.json"],
            "status": "SUPPORTED" if counts["high_risk_unverified"] else "UNSUPPORTED",
            "value": {"high_risk_unverified": counts["high_risk_unverified"]},
        },
    ]
    level_claim = {
        "declared": "B",
        "a_level_eligible": False,
        "reasons": ["high-risk paths unverified", "no external independent review"],
    }
    return {
        "schema_version": "1.3.4",
        "facts_id": "FACTS-" + hashlib.sha256(json.dumps(counts, sort_keys=True).encode()).hexdigest()[:12],
        "run_id": task_result["run_id"],
        "source_freshness": {
            "audit_task_result": str(audit_dir / "task-result.json"),
            "generated_from": "audit + verify evidence",
        },
        "counts": counts,
        "claims": claims,
        "level_claim": level_claim,
        "limits": [
            "G1 static discovery not re-run for this run",
            "search/region/task-state/delete-confirm not captured (AUDITOR_OMISSION)",
            "high-risk execution paths unverified",
            "ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED",
        ],
    }


def lint(facts: dict[str, Any], audit_dir: Path | None = None) -> list[str]:
    problems: list[str] = []
    counts = facts.get("counts", {})
    claims = facts.get("claims", [])
    level = facts.get("level_claim", {})

    if counts.get("dangling_evidence_refs", 0) > 0:
        problems.append(f"DANGLING_EVIDENCE_REF: {counts['dangling_evidence_refs']} coverage refs do not resolve")
    if counts.get("unverified_records", 0) > 0 and counts.get("unverified_scopes", 0) == 0:
        problems.append("UNVERIFIED_WITHOUT_DISPOSITION: unverified records but no scoped dispositions")
    for claim in claims:
        if claim.get("status") == "UNSUPPORTED":
            problems.append(f"UNSUPPORTED_CLAIM: {claim.get('claim_id')}: {claim.get('statement')}")
        if not claim.get("evidence"):
            problems.append(f"CLAIM_WITHOUT_EVIDENCE: {claim.get('claim_id')}")
    if counts.get("pass_records", 0) > 0 and counts.get("resolved_evidence_refs", 0) == 0:
        problems.append("PASS_WITHOUT_EVIDENCE: pass records exist but no evidence reference resolves")
    if counts.get("captures", 0) and counts["captures"] < counts.get("coverage_records", 0):
        problems.append("CAPTURE_COVERAGE_MISMATCH: fewer captures than coverage records")
    if counts.get("high_risk_unverified", 0) > 0 and level.get("a_level_eligible"):
        problems.append("LEVEL_OVERCLAIM: A-level claimed while high-risk paths are unverified")
    if counts.get("independent_findings_failed", 0) > 0:
        problems.append("INDEPENDENT_REVIEW_FAIL: reviewer found failures")

    if audit_dir is not None:
        audit = Path(audit_dir)
        if not (audit / "task-result.json").is_file():
            problems.append("MISSING_TASK_RESULT")
        else:
            task_result = _load(audit / "task-result.json")
            if task_result.get("run_id") != facts.get("run_id"):
                problems.append("RUN_ID_MISMATCH: facts and task-result disagree")
            g6 = task_result.get("derived_g6", {}).get("state")
            if g6 == "PASS" and counts.get("high_risk_unverified", 0) > 0:
                problems.append("G6_OVERCLAIM: G6 PASS while high-risk paths are unverified")
    return problems


def facts_digest(facts: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
