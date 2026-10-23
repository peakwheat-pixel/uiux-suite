from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT

from uiux_engine import integrity, safety, vault

SCENARIO = REPO_ROOT / "tests" / "fixtures" / "scenarios" / "complete-redesign"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_for(tmp_path: Path) -> tuple[dict, Path]:
    root = tmp_path / "evidence-root"
    root.mkdir()
    manifest = json.loads((SCENARIO / "evidence-manifest.json").read_text(encoding="utf-8"))
    for index, item in enumerate(manifest["items"]):
        rel = f"ev-{index}.json"
        path = root / rel
        path.write_text(json.dumps({"id": item["id"]}), encoding="utf-8")
        item["references"] = [rel]
        item["source_sha256"] = sha(path)
        item["redacted_sha256"] = sha(path)
    return manifest, root


def test_all_available_evidence_verifies(tmp_path: Path):
    manifest, root = manifest_for(tmp_path)
    report = vault.verify(manifest, root)
    assert report["ok"] is True
    assert len(report["verified"]) == len(manifest["items"])


def test_tampered_evidence_is_invalid_and_quarantined(tmp_path: Path):
    manifest, root = manifest_for(tmp_path)
    target = root / "ev-2.json"
    target.write_text("tampered", encoding="utf-8")
    quarantine = tmp_path / "quarantine"
    report = vault.verify(manifest, root, quarantine_dir=quarantine)
    assert report["ok"] is False
    assert any(entry["id"] == manifest["items"][2]["id"] for entry in report["invalid"])
    assert report["quarantined"]


def test_missing_evidence_is_reported(tmp_path: Path):
    manifest, root = manifest_for(tmp_path)
    (root / "ev-0.json").unlink()
    report = vault.verify(manifest, root)
    assert report["ok"] is False
    assert any(entry["id"] == manifest["items"][0]["id"] for entry in report["missing"])


def test_non_available_items_are_skipped(tmp_path: Path):
    manifest, root = manifest_for(tmp_path)
    for item in manifest["items"]:
        item["status"] = "REDACTED_ONLY"
    report = vault.verify(manifest, root)
    assert report["ok"] is True
    assert report["verified"] == []


def records() -> list[dict]:
    return [{"probe_id": "P1", "exit_code": 0}, {"probe_id": "P2", "exit_code": 0}]


def test_hash_chain_verifies_and_detects_tamper():
    chain = integrity.build_chain(records())
    assert integrity.verify_chain(chain) == []
    chain[1]["record"]["exit_code"] = 1
    assert integrity.verify_chain(chain)


def test_chain_head_changes_with_content():
    first = integrity.chain_head(integrity.build_chain(records()))
    second = integrity.chain_head(integrity.build_chain(records() + [{"probe_id": "P3"}]))
    assert first != second


def test_attestation_head_mismatch_is_rejected():
    attestation = {"reviewed_head": "a" * 40, "isolation_level": "INDEPENDENT_SESSION", "review_origin": {"trust_source": "host_verified", "verification_evidence": ["x"]}}
    problems = integrity.verify_attestation_binding(attestation, "b" * 40)
    assert any("reviewed_head" in problem for problem in problems)


def test_self_attested_independence_is_rejected():
    attestation = {"reviewed_head": "a" * 40, "isolation_level": "INDEPENDENT_SESSION", "review_origin": {"trust_source": "user_attested"}}
    problems = integrity.verify_attestation_binding(attestation, "a" * 40)
    assert any("user-attested" in problem for problem in problems)


def test_host_verified_requires_evidence():
    attestation = {"reviewed_head": "a" * 40, "isolation_level": "INDEPENDENT_SESSION", "review_origin": {"trust_source": "host_verified"}}
    problems = integrity.verify_attestation_binding(attestation, "a" * 40)
    assert any("verification_evidence" in problem for problem in problems)


def test_classify_create_is_p1():
    result = safety.classify_plan({"changes": [{"action": "create", "path": "src/a.ts"}]})
    assert result["level"] == safety.P1
    assert result["allowed_without_user"] is True


def test_classify_modify_is_p2():
    result = safety.classify_plan({"changes": [{"action": "modify", "path": "src/a.ts"}]})
    assert result["level"] == safety.P2


def test_classify_delete_requires_confirmation():
    result = safety.classify_plan({"changes": [{"action": "delete", "path": "src/a.ts"}]})
    assert result["level"] == safety.P3
    assert result["requires_confirmation"] is True


def test_zero_real_user_data_metrics():
    report = safety.metrics([{"real_user_data_writes": 0, "protected_root_writes": 0, "blocked_actions": 1, "actions": []}])
    assert report["zero_real_user_data_writes"] is True
    assert report["blocked_actions"] == 1


def test_write_outside_root_is_flagged(tmp_path: Path):
    problems = safety.audit_write_targets(tmp_path, ["../outside.txt", "inside.txt"])
    assert problems and "outside" in problems[0]
