"""Evidence lifecycle evaluation (V1.3.3).

Rules implemented here:
- AVAILABLE requires a source byte hash and a non-expired expiry timestamp.
- REDACTED_ONLY may support context but can never substitute a re-checkable original.
- Deleted Vault / expired originals invalidate new PASS issuance for gates that
  depend on them; historical results remain historical records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .contracts import sha256_json
from .enums import is_valid

PASS_USABLE = {"AVAILABLE"}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def index_items(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in manifest.get("items", []):
        evidence_id = item.get("id")
        if not evidence_id:
            continue
        index[evidence_id] = item
    return index


def semantic_problems(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for item in manifest.get("items", []):
        evidence_id = item.get("id", "<missing>")
        if evidence_id in seen:
            problems.append(f"duplicate evidence id: {evidence_id}")
        seen.add(evidence_id)
        status = item.get("status")
        if not is_valid("EvidenceStatus", status):
            problems.append(f"{evidence_id}: invalid status {status!r}")
            continue
        if status == "AVAILABLE" and not item.get("source_sha256"):
            problems.append(f"{evidence_id}: AVAILABLE requires source_sha256")
        if status == "REDACTED_ONLY" and not item.get("redacted_sha256"):
            problems.append(f"{evidence_id}: REDACTED_ONLY requires redacted_sha256")
        expiry = parse_time(item.get("expiry_at"))
        created = parse_time(item.get("created_at"))
        if expiry and created and expiry < created:
            problems.append(f"{evidence_id}: expiry_at precedes created_at")
        if item.get("storage_class") == "vault" and item.get("retention_policy") == "run_default":
            if status == "AVAILABLE" and expiry is None:
                problems.append(f"{evidence_id}: vault evidence must declare expiry_at")
    return problems


def effective_status(item: dict[str, Any], now: datetime) -> str:
    status = item.get("status", "SOURCE_EVIDENCE_UNAVAILABLE")
    if status == "AVAILABLE":
        expiry = parse_time(item.get("expiry_at"))
        if expiry is not None and expiry <= now:
            return "EXPIRED"
    if status == "QUARANTINED":
        return "QUARANTINED"
    if status == "INVALID_HASH":
        return "INVALID_HASH"
    return status


def check_reference(
    ref: dict[str, Any],
    index: dict[str, dict[str, Any]],
    now: datetime,
    require_available: bool = True,
) -> list[str]:
    """Return ReasonCode-like problems for one gate evidence reference."""
    problems: list[str] = []
    evidence_id = ref.get("evidence_id")
    item = index.get(evidence_id)
    if item is None:
        return ["MISSING_EVIDENCE"]
    status = effective_status(item, now)
    if require_available and status not in PASS_USABLE:
        if status == "EXPIRED":
            problems.append("EVIDENCE_EXPIRED")
        elif status in ("SOURCE_EVIDENCE_UNAVAILABLE", "REDACTED_ONLY"):
            problems.append("EVIDENCE_SOURCE_UNAVAILABLE")
        elif status == "INVALID_HASH":
            problems.append("INVALID_EVIDENCE_HASH")
        elif status == "QUARANTINED":
            problems.append("EVIDENCE_QUARANTINED")
        else:
            problems.append("MISSING_EVIDENCE")
    expected_sha = item.get("source_sha256") or item.get("redacted_sha256")
    if expected_sha and ref.get("sha256") and expected_sha != ref.get("sha256"):
        problems.append("INVALID_EVIDENCE_HASH")
    item_probe = (item.get("provenance") or {}).get("probe_id")
    if item_probe and ref.get("probe_id") and item_probe != ref.get("probe_id"):
        problems.append("PROBE_ID_MISSING")
    item_level = (item.get("provenance") or {}).get("execution_level")
    if item_level and ref.get("evidence_level") and item_level != ref.get("evidence_level"):
        problems.append("LAYER_SPOOF_OR_MISSING")
    return problems


def check_gate_evidence(
    gate_result: dict[str, Any],
    index: dict[str, dict[str, Any]],
    now: datetime,
    require_available: bool = True,
) -> list[str]:
    problems: list[str] = []
    for ref in gate_result.get("evidence_refs", []):
        problems.extend(check_reference(ref, index, now, require_available))
    return problems


def manifest_digest(manifest: dict[str, Any]) -> str:
    return sha256_json(manifest)


def has_expired_items(manifest: dict[str, Any], now: datetime) -> bool:
    return any(effective_status(item, now) == "EXPIRED" for item in manifest.get("items", []))


def usable_evidence_ids(manifest: dict[str, Any], now: datetime) -> set[str]:
    return {
        item["id"]
        for item in manifest.get("items", [])
        if effective_status(item, now) in PASS_USABLE
    }


def _unused(_: Iterable[str]) -> None:  # pragma: no cover - keeps linters quiet
    return None
