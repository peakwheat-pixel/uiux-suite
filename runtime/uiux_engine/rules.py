"""Frozen rule catalog and exemption handling (Stage 1 / T1.0)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import contracts
from .enums import SUITE_ROOT, is_valid, values

RULES_DIR = SUITE_ROOT / "knowledge" / "rules"
CATALOG_PATH = RULES_DIR / "catalog.v1.0.json"
FREEZE_PATH = RULES_DIR / "catalog.v1.0.freeze.json"


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    return contracts.load_json(path or CATALOG_PATH)


def canonical_digest(catalog: dict[str, Any]) -> str:
    return contracts.sha256_json(catalog)


def semantic_problems(catalog: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    problems.extend(contracts.validation_errors("rule-catalog", catalog))
    if problems:
        return problems
    seen: set[str] = set()
    for rule in catalog["rules"]:
        rule_id = rule["rule_id"]
        if rule_id in seen:
            problems.append(f"duplicate rule_id: {rule_id}")
        seen.add(rule_id)
        if rule["severity"] not in values("RuleSeverity"):
            problems.append(f"{rule_id}: severity not in RuleSeverity")
        if rule["category"] not in values("RuleCategory"):
            problems.append(f"{rule_id}: category not in RuleCategory")
        if rule["detector"] not in values("DetectorKind"):
            problems.append(f"{rule_id}: detector not in DetectorKind")
    return problems


def freeze_record(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    return {
        "catalog_version": catalog["catalog_version"],
        "rules_count": len(catalog["rules"]),
        "sha256": canonical_digest(catalog),
    }


def verify_frozen(freeze_path: str | Path | None = None) -> list[str]:
    path = Path(freeze_path) if freeze_path else FREEZE_PATH
    if not path.is_file():
        return [f"freeze record missing: {path}"]
    frozen = contracts.load_json(path)
    current = freeze_record()
    problems: list[str] = []
    for key in ("catalog_version", "rules_count", "sha256"):
        if frozen.get(key) != current[key]:
            problems.append(f"freeze mismatch: {key} expected {frozen.get(key)!r} got {current[key]!r}")
    return problems


def check_exemption(exemption: dict[str, Any], now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    problems = contracts.validation_errors("rule-exemption", exemption)
    if problems:
        return problems
    known = {rule["rule_id"] for rule in load_catalog()["rules"]}
    if exemption["rule_id"] not in known:
        problems.append(f"unknown rule_id: {exemption['rule_id']}")
    created = _time(exemption["created_at"])
    expires = _time(exemption["expires_at"])
    if created and created > now:
        problems.append("exemption created_at is in the future")
    if expires is None or expires <= now:
        problems.append("exemption expired")
    if created and expires and created > expires:
        problems.append("exemption created_at is after expires_at")
    return problems


def _time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def active_exemptions(exemptions: list[dict[str, Any]], now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for exemption in exemptions:
        if check_exemption(exemption, now):
            continue
        result.setdefault(exemption["rule_id"], []).append(exemption)
    return result


def is_valid_rule_id(rule_id: str) -> bool:
    return is_valid("rule-catalog", {"schema_version": "1.3.3", "catalog_version": "1.0", "rules": [
        {
            "rule_id": rule_id,
            "title": "x",
            "category": "A11Y",
            "severity": "INFO",
            "detector": "style_token_linter",
            "scope": ["any"],
            "description": "x",
            "remediation": "x",
            "evidence_kind": "other",
            "enabled": True,
        }
    ]})
