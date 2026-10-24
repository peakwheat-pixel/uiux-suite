"""Defect attribution and false-positive control (TASK-04, V1.3.4).

Rules:
- No attribution without evidence: missing/unresolvable evidence can never be
  classified as a product defect.
- Environment-authored findings (A/B control) are ENVIRONMENT, not PRODUCT.
- Uncaptured scope is AUDITOR_OMISSION, not a product pass and not an
  environment excuse.
- P0/P1 findings must carry the full attribution record before they may be
  reported as confirmed.
- A reviewer may retract a sub-conclusion; retracted findings are excluded from
  confirmed counts but kept in the record.
"""
from __future__ import annotations

import json
from typing import Any

CATEGORIES = ("PRODUCT", "ENVIRONMENT", "AUDITOR_OMISSION", "TOOLING", "UNCERTAIN")
DISPOSITIONS = ("CONFIRMED", "PARTIAL", "UNVERIFIED", "ENVIRONMENT_AUTHored", "REJECTED")
P0P1_FIELDS = (
    "id", "severity", "title", "attribution", "disposition", "evidence_refs",
    "reproduction", "root_cause", "impact", "verification",
)


def validate_issue(issue: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    severity = issue.get("severity")
    if severity in ("P0", "P1"):
        missing = [field for field in P0P1_FIELDS if not issue.get(field)]
        if missing:
            problems.append(f"{issue.get('id', '<no-id>')}: missing P0/P1 attribution fields: {missing}")
    if issue.get("attribution") not in CATEGORIES:
        problems.append(f"{issue.get('id', '<no-id>')}: invalid attribution {issue.get('attribution')!r}")
    if issue.get("disposition") not in DISPOSITIONS:
        problems.append(f"{issue.get('id', '<no-id>')}: invalid disposition {issue.get('disposition')!r}")
    if issue.get("attribution") == "PRODUCT" and not issue.get("evidence_refs"):
        problems.append(f"{issue.get('id', '<no-id>')}: PRODUCT attribution requires evidence")
    if issue.get("disposition") == "CONFIRMED" and issue.get("attribution") in ("UNCERTAIN", "ENVIRONMENT"):
        problems.append(f"{issue.get('id', '<no-id>')}: confirmed findings cannot be uncertain/environment")
    return problems


def classify(
    *,
    has_evidence: bool,
    environment_only: bool = False,
    product_signal: bool = False,
    captured: bool = True,
) -> str:
    """Deterministic classification used by tests and by the auditor review."""
    if not has_evidence:
        return "UNCERTAIN"
    if environment_only and not product_signal:
        return "ENVIRONMENT"
    if not captured:
        return "AUDITOR_OMISSION"
    if product_signal:
        return "PRODUCT"
    return "UNCERTAIN"


def attribution_stats(issues: list[dict[str, Any]]) -> dict[str, Any]:
    confirmed = [i for i in issues if i.get("disposition") == "CONFIRMED"]
    by_category: dict[str, int] = {category: 0 for category in CATEGORIES}
    for issue in issues:
        category = issue.get("attribution", "UNCERTAIN")
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "total": len(issues),
        "confirmed": len(confirmed),
        "rejected": len([i for i in issues if i.get("disposition") == "REJECTED"]),
        "by_category": by_category,
        "p0p1": len([i for i in issues if i.get("severity") in ("P0", "P1")]),
        "p0p1_confirmed": len([i for i in confirmed if i.get("severity") in ("P0", "P1")]),
    }


def merge_with_reviewer(auditor_issues: dict[str, Any], reviewer_findings: dict[str, list[str]]) -> dict[str, Any]:
    """Apply reviewer retractions (finding_id -> list of issues to retract)."""
    merged = json.loads(json.dumps(auditor_issues, ensure_ascii=False))
    retracted: list[str] = []
    by_id = {issue["id"]: issue for issue in merged["issues"]}
    for finding_id, issue_ids in reviewer_findings.items():
        for issue_id in issue_ids:
            issue = by_id.get(issue_id)
            if issue is None:
                continue
            issue["disposition"] = "REJECTED"
            issue.setdefault("reviewer_note", f"retracted by {finding_id}")
            retracted.append(issue_id)
    merged["reviewer_retractions"] = retracted
    return merged


def lint_issues(issues: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for issue in issues.get("issues", []):
        problems.extend(validate_issue(issue))
    # cross-check: unverified scopes must be labelled AUDITOR_OMISSION/NATIVE
    for scope in issues.get("unverified_scopes", []):
        if not scope.get("disposition"):
            problems.append(f"UNVERIFIED_WITHOUT_DISPOSITION: {scope.get('scope_ref')}")
    # a confirmed P0/P1 requires verification evidence
    for issue in issues.get("issues", []):
        if issue.get("severity") in ("P0", "P1") and issue.get("disposition") == "CONFIRMED":
            if not issue.get("verification"):
                problems.append(f"{issue.get('id')}: confirmed P0/P1 lacks verification")
    return problems
