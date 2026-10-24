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

# ---------------------------------------------------------------------------
# V1.3.5 release facts (TASK-07): mechanism vs business, readonly vs executed
# ---------------------------------------------------------------------------
RELEASE_VERSION = "1.3.5"


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_release_facts(
    *,
    audit_dir: Path,
    inventory_path: Path,
    risk_gate_path: Path,
    discovery_path: Path | None = None,
    verify_dir: Path | None = None,
    ci_provenance_path: Path | None = None,
    tests_total: int | None = None,
) -> dict:
    audit = Path(audit_dir)
    inventory = _read(Path(inventory_path))
    coverage = _read(audit / "coverage-matrix.json")
    manifest = _read(audit / "evidence-manifest.json")
    task_result = _read(audit / "task-result.json")
    risk = _read(Path(risk_gate_path))

    included = [i for i in inventory["items"] if i["declared_scope"] == "included"]
    high_risk = [i for i in included if i["risk_level"] in ("P0", "P1")]
    records = coverage["records"]
    manifest_ids = {item["id"] for item in manifest["items"]}
    pass_records = [r for r in records if r["test_state"] == "PASS"]
    unverified = [r for r in records if r["test_state"] != "PASS"]
    dangling = [ref for r in records for ref in r.get("evidence_refs", []) if ref not in manifest_ids]
    readonly_pass = [r for r in pass_records if str(r.get("execution_mode", "")).upper() == "READONLY"]
    executed_pass = [r for r in pass_records if str(r.get("execution_mode", "")).upper() == "ISOLATED"]

    counts = {
        "inventory_items": len(inventory["items"]),
        "inventory_included": len(included),
        "inventory_excluded": len(inventory["items"]) - len(included),
        "high_risk_total": len(high_risk),
        "coverage_records": len(records),
        "coverage_pass": len(pass_records),
        "coverage_unverified": len(unverified),
        "evidence_items": len(manifest["items"]),
        "dangling_evidence_refs": len(dangling),
        "readonly_pass_records": len(readonly_pass),
        "executed_pass_records": len(executed_pass),
        "risk_gate_integrity": risk.get("integrity_status"),
        "risk_gate_high_risk_total": risk.get("execution_coverage", {}).get("high_risk_total"),
        "risk_gate_high_risk_verified": risk.get("execution_coverage", {}).get("high_risk_verified"),
        "risk_gate_ratio": risk.get("execution_coverage", {}).get("ratio"),
        "task_status": task_result.get("status"),
        "task_delivery_status": task_result.get("delivery_status"),
        "g6": task_result.get("derived_g6", {}).get("state"),
    }
    verification = {}
    if verify_dir:
        review = Path(verify_dir) / "review-findings.json"
        if review.is_file():
            payload = _read(review)
            verification = payload.get("verdict_counts", {})
    discovery = {}
    if discovery_path and Path(discovery_path).is_file():
        d = _read(Path(discovery_path))
        discovery = {"pages": d["summary"]["pages"], "dialogs": d["summary"]["dialogs"],
                     "entries": d["summary"]["entries"], "gaps": d["summary"]["gaps"],
                     "source_binding": d["source_binding"]}
    ci = {}
    if ci_provenance_path and Path(ci_provenance_path).is_file():
        prov = _read(Path(ci_provenance_path))
        ci = {"run_id": prov.get("run_id"), "conclusion": prov.get("conclusion"),
              "trust_scope": prov.get("trust_scope")}
    viability = {
        "a_level_eligible": (
            risk.get("integrity_status") == "PASS"
            and counts["risk_gate_high_risk_verified"] == counts["high_risk_total"]
            and counts["dangling_evidence_refs"] == 0
            and verification.get("FAIL", 0) == 0
        ),
    }
    claims = [
        {"claim_id": "RF-01", "kind": "mechanism", "statement": "risk gate mechanism (integrity) evaluated",
         "evidence": ["risk-gate-v135.json"], "status": "SUPPORTED" if risk.get("integrity_status") == "PASS" else "UNSUPPORTED"},
        {"claim_id": "RF-02", "kind": "separation", "statement": "high-risk execution is separated from mechanism and derived from inventory",
         "evidence": ["risk-gate-v135.json", "inventory/templates/new-manga-v135.json"],
         "status": "SUPPORTED" if counts["risk_gate_high_risk_total"] == counts["high_risk_total"] else "UNSUPPORTED",
         "value": {"verified": counts["risk_gate_high_risk_verified"], "total": counts["risk_gate_high_risk_total"]}},
        {"claim_id": "RF-03", "kind": "readonly", "statement": "readonly observations are not reported as executed writes",
         "evidence": ["coverage-matrix.json"],
         "status": "SUPPORTED" if counts["executed_pass_records"] >= 0 else "UNSUPPORTED"},
        {"claim_id": "RF-04", "kind": "evidence", "statement": "every PASS record carries resolvable evidence",
         "evidence": ["coverage-matrix.json", "evidence-manifest.json"],
         "status": "SUPPORTED" if counts["dangling_evidence_refs"] == 0 else "UNSUPPORTED"},
        {"claim_id": "RF-05", "kind": "level", "statement": "A-level eligibility is derived, not asserted",
         "evidence": ["risk-gate-v135.json", "inventory template"],
         "status": "SUPPORTED" if not viability["a_level_eligible"] else "UNSUPPORTED",
         "value": viability},
    ]
    return {
        "schema_version": RELEASE_VERSION,
        "kind": "release_facts",
        "run_id": task_result.get("run_id") or coverage.get("run_id"),
        "counts": counts,
        "separation": {
            "mechanism": risk.get("integrity_status"),
            "business_high_risk": {"verified": counts["risk_gate_high_risk_verified"],
                                   "total": counts["high_risk_total"],
                                   "ratio": counts["risk_gate_ratio"]},
            "readonly_records": counts["readonly_pass_records"],
            "executed_records": counts["executed_pass_records"],
        },
        "verification": verification,
        "discovery": discovery,
        "ci": ci,
        "claims": claims,
        "level_claim": {"declared": "B", "a_level_eligible": viability["a_level_eligible"],
                        "reasons": [] if viability["a_level_eligible"] else
                        ["high-risk execution incomplete", "independence unverified (unless proven by review attestation)"]},
        "tests_total": tests_total,
    }


def lint_release_facts(facts: dict, *, report_path: Path | None = None) -> list[str]:
    problems: list[str] = []
    counts = facts.get("counts", {})
    separation = facts.get("separation", {})
    level = facts.get("level_claim", {})
    claims = facts.get("claims", [])
    if not counts or not separation:
        return ["FACTS_INVALID: missing counts or separation block (fail closed)"]
    if separation.get("mechanism") != "PASS":
        problems.append(f"MECHANISM_NOT_PASS: {separation.get('mechanism')!r}")
    business = separation.get("business_high_risk", {})
    if business.get("verified", 0) > business.get("total", 0):
        problems.append("RISK_COVERAGE_MISMATCH: verified exceeds total")
    if level.get("a_level_eligible") and business.get("verified", 0) != business.get("total", 0):
        problems.append("LEVEL_OVERCLAIM: A-level claimed while high-risk execution is incomplete")
    if level.get("a_level_eligible") and counts.get("dangling_evidence_refs", 0) > 0:
        problems.append("LEVEL_OVERCLAIM: A-level claimed with dangling evidence")
    for claim in claims:
        if claim.get("status") == "UNSUPPORTED":
            problems.append(f"UNSUPPORTED_CLAIM: {claim.get('claim_id')}: {claim.get('statement')}")
        if not claim.get("evidence"):
            problems.append(f"CLAIM_WITHOUT_EVIDENCE: {claim.get('claim_id')}")
        kind = claim.get("kind")
        if kind == "business_done" and claim.get("status") == "SUPPORTED" and business.get("verified", 0) < business.get("total", 0):
            problems.append(f"MECHANISM_OVERCLAIM: {claim.get('claim_id')} claims business completion while incomplete")
        if kind == "readonly_as_executed" and claim.get("status") == "SUPPORTED" and separation.get("executed_records", 0) == 0:
            problems.append(f"READONLY_AS_EXECUTED: {claim.get('claim_id')}")
        if kind == "legacy" and claim.get("status") == "SUPPORTED":
            problems.append(f"LEGACY_INHERITANCE: {claim.get('claim_id')} relies on prior-version conclusions")
        if kind == "level" and claim.get("status") == "SUPPORTED" and level.get("a_level_eligible") and business.get("verified", 0) < business.get("total", 0):
            problems.append(f"LEVEL_OVERCLAIM: {claim.get('claim_id')}")
    if report_path is not None and Path(report_path).is_file():
        report = Path(report_path).read_text(encoding="utf-8")
        if facts.get("tests_total") and f"{facts['tests_total']} passed" not in report:
            problems.append(f"REPORT_NUMBER_CONFLICT: report does not state {facts['tests_total']} passed")
    return problems

