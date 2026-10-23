"""Evidence integrity: hash-chained tool logs and attestation binding (T3.6)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS = "0" * 64


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_chain(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chain = []
    previous = GENESIS
    for record in records:
        digest = hashlib.sha256((_canonical(record) + previous).encode("utf-8")).hexdigest()
        chain.append({"record": record, "previous": previous, "digest": digest})
        previous = digest
    return chain


def chain_head(chain: list[dict[str, Any]]) -> str:
    return chain[-1]["digest"] if chain else GENESIS


def verify_chain(chain: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    previous = GENESIS
    for index, link in enumerate(chain):
        if link.get("previous") != previous:
            problems.append(f"chain[{index}]: previous mismatch")
        expected = hashlib.sha256((_canonical(link["record"]) + previous).encode("utf-8")).hexdigest()
        if link.get("digest") != expected:
            problems.append(f"chain[{index}]: digest mismatch")
        previous = link.get("digest", "")
    return problems


def verify_attestation_binding(attestation: dict[str, Any], git_commit: str | None) -> list[str]:
    problems: list[str] = []
    if git_commit and attestation.get("reviewed_head") != git_commit:
        problems.append("attestation reviewed_head does not match current commit")
    origin = attestation.get("review_origin") or {}
    if attestation.get("isolation_level") == "INDEPENDENT_SESSION" and origin.get("trust_source") in (None, "none", "user_attested"):
        problems.append("independent claim is only user-attested")
    if attestation.get("isolation_level") == "INDEPENDENT_SESSION" and origin.get("trust_source") == "host_verified":
        if not origin.get("verification_evidence"):
            problems.append("host_verified attestation lacks verification_evidence")
    return problems


def verify_report(records: list[dict[str, Any]], attestation: dict[str, Any], git_commit: str | None) -> dict[str, Any]:
    chain = build_chain(records)
    problems = verify_chain(chain) + verify_attestation_binding(attestation, git_commit)
    return {"ok": not problems, "problems": problems, "head": chain_head(chain), "links": len(chain)}
