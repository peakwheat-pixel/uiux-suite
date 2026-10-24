"""TASK-00: dual-contract version dispatch and V1.3.3 semantic regression.

Rules under test:
- Both contract sets load independently and stay self-contained.
- The schema version is inferred from the instance; unknown versions fail closed.
- An instance without a version fails closed (schema_version is required).
- Mixed-version finalize inputs are rejected.
- V1.3.3 inputs reproduce the legacy semantics exactly (PARTIAL / G6 UNVERIFIED /
  aggregate NONE / delivery PARTIAL_VERIFIED).
- V1.3.4 inputs use the new disposition/delivery-dimension semantics.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from conftest import load_fixture
from uiux_engine import contracts, evidence, gates
from uiux_engine.evidence import parse_time

NOW = "2026-10-24T03:22:00+00:00"
REAL_AUDIT = Path(r"G:\AI\uiux-acceptance-v133\evidence\audit")

REQUEST = load_fixture("contracts/valid/task-request-redesign.json")
GATE_RESULTS = load_fixture("contracts/valid/gate-results.json")
COVERAGE = load_fixture("contracts/valid/coverage-matrix.json")
MANIFEST = load_fixture("contracts/valid/evidence-manifest.json")
TOOL_LOGS = load_fixture("scenarios/complete-redesign/tool-logs.json")
DESIGN_REVIEW = load_fixture("contracts/valid/design-review.json")
ATTESTATION = load_fixture("contracts/valid/review-attestation.json")


def _evaluate(**overrides):
    params = {
        "request": copy.deepcopy(REQUEST),
        "gate_results": copy.deepcopy(GATE_RESULTS),
        "coverage": copy.deepcopy(COVERAGE),
        "manifest": copy.deepcopy(MANIFEST),
        "tool_logs": copy.deepcopy(TOOL_LOGS),
        "design_review": copy.deepcopy(DESIGN_REVIEW),
        "review_attestation": copy.deepcopy(ATTESTATION),
        "warn_reviews": [],
        "now": parse_time(NOW),
    }
    params.update(overrides)
    if "request" in overrides or "gate_results" in overrides:
        params["gate_results"]["request_digest"] = contracts.sha256_json(params["request"])
    return gates.evaluate_run(**params)


# ---------------------------------------------------------------- schema layers


def test_both_contract_sets_are_complete_and_self_contained():
    for version in contracts.SUPPORTED_SCHEMA_VERSIONS:
        files = contracts.schema_files(version)
        assert len(files) == 26, f"{version}: expected 26 schemas, got {len(files)}"
        for name in files:
            doc = contracts.schema_document(name, version)
            assert doc.get("$id", "").endswith(files[name]), f"{version}/{name}: $id mismatch"
            refs = json.dumps(doc)
            if version == "1.3.3":
                assert "v1.3.4.schema.json" not in refs
            else:
                assert "v1.3.3.schema.json" not in refs


def test_v133_instance_infers_v133_schema():
    instance = copy.deepcopy(REQUEST)
    assert contracts.validation_errors("task-request", instance) == []
    # explicit cross-version validation must not silently accept the old contract
    assert contracts.validation_errors("task-request", instance, "1.3.4")


def test_unversioned_instance_fails_closed():
    instance = copy.deepcopy(REQUEST)
    del instance["schema_version"]
    errors = contracts.validation_errors("task-request", instance)
    assert errors, "an instance without schema_version must not validate"
    assert any("schema_version" in error for error in errors)


def test_unsupported_version_is_rejected_explicitly():
    instance = copy.deepcopy(REQUEST)
    instance["schema_version"] = "9.9.9"
    errors = contracts.validation_errors("task-request", instance)
    assert errors
    assert any("SCHEMA_VERSION_UNSUPPORTED" in error for error in errors)


def test_version_consistency_helper_reports_missing_and_mixed():
    problems = contracts.version_consistency_errors(
        "1.3.4",
        {"unversioned": {"a": 1}, "mixed": {"schema_version": "1.3.3"}},
    )
    text = "\n".join(problems)
    assert "SCHEMA_VERSION_MISSING" in text
    assert "SCHEMA_VERSION_MISMATCH" in text


def test_mixed_version_finalize_is_rejected():
    request = copy.deepcopy(REQUEST)
    request["schema_version"] = "1.3.4"
    outcome = _evaluate(request=request)
    codes = {reason["code"] for reason in outcome["blocking_reasons"]}
    assert "SCHEMA_VERSION_MISMATCH" in codes
    assert outcome["status"] != "COMPLETE"


# ------------------------------------------------- V1.3.3 legacy semantics


def test_v133_legacy_semantics_unchanged():
    outcome = _evaluate()
    assert outcome["schema_version"] == "1.3.3"
    assert outcome["status"] == "COMPLETE"
    assert "delivery_dimensions" not in outcome, "V1.3.3 results must not gain V1.3.4 fields"
    assert "scope_summary" not in outcome


def test_v133_unverified_record_forces_none_aggregate():
    coverage = copy.deepcopy(COVERAGE)
    coverage["records"][0]["test_state"] = "UNVERIFIED"
    outcome = _evaluate(coverage=coverage)
    assert outcome["runtime_evidence_level"] == "NONE"
    assert outcome["status"] != "COMPLETE"
    assert {p["reason_code"] for p in outcome["unverified_paths"]} == {"UNVERIFIED_PATH"}


@pytest.mark.skipif(not REAL_AUDIT.is_dir(), reason="V1.3.3 acceptance evidence not present on this host")
def test_v133_real_acceptance_inputs_reproduce_partial():
    def load(name):
        return json.loads((REAL_AUDIT / name).read_text(encoding="utf-8"))

    outcome = gates.evaluate_run(
        request=load("task-request.json"),
        gate_results=load("gate-results.json"),
        coverage=load("coverage-matrix.json"),
        manifest=load("evidence-manifest.json"),
        tool_logs=load("tool-logs.json"),
        design_review=load("design-review.json"),
        review_attestation=None,
        warn_reviews=[],
        now=parse_time(NOW),
    )
    assert outcome["schema_version"] == "1.3.3"
    assert outcome["status"] == "PARTIAL"
    assert outcome["delivery_status"] == "PARTIAL_VERIFIED"
    assert outcome["derived_g6"]["state"] == "UNVERIFIED"
    assert outcome["runtime_evidence_level"] == "NONE"
    assert outcome["unverified_paths"], "the real V1.3.3 run had unverified paths"


# ------------------------------------------------- V1.3.4 new semantics


def _v134_inputs(*, dispositions: list[str | None], risk: bool = False):
    request = copy.deepcopy(REQUEST)
    request["schema_version"] = "1.3.4"
    gate_results = copy.deepcopy(GATE_RESULTS)
    gate_results["schema_version"] = "1.3.4"
    coverage = copy.deepcopy(COVERAGE)
    coverage["schema_version"] = "1.3.4"
    manifest = copy.deepcopy(MANIFEST)
    manifest["schema_version"] = "1.3.4"
    tool_logs = copy.deepcopy(TOOL_LOGS)
    for log in tool_logs:
        log["schema_version"] = "1.3.4"
    design_review = copy.deepcopy(DESIGN_REVIEW)
    design_review["schema_version"] = "1.3.4"
    attestation = copy.deepcopy(ATTESTATION)
    attestation["schema_version"] = "1.3.4"
    attestation["evidence_manifest_hash"] = evidence.manifest_digest(manifest)
    records = coverage["records"]
    for index, disposition in enumerate(dispositions):
        if index >= len(records):
            break
        if disposition is None:
            continue
        records[index]["test_state"] = "UNVERIFIED"
        records[index]["disposition"] = disposition
        if risk:
            records[index]["risk_ref"] = "RISK-001"
    return {
        "request": request,
        "gate_results": gate_results,
        "coverage": coverage,
        "manifest": manifest,
        "tool_logs": tool_logs,
        "design_review": design_review,
        "review_attestation": attestation,
        "warn_reviews": [],
        "now": parse_time(NOW),
        "schema_version": "1.3.4",
    }


def test_v134_environment_unavailable_is_excluded_from_aggregate():
    params = _v134_inputs(dispositions=["ENVIRONMENT_UNAVAILABLE"])
    params["gate_results"]["request_digest"] = contracts.sha256_json(params["request"])
    outcome = gates.evaluate_run(**params)
    assert outcome["schema_version"] == "1.3.4"
    # the excluded record must not drag the aggregate to NONE
    assert outcome["runtime_evidence_level"] != "NONE"
    assert outcome["unverified_paths"][0]["reason_code"] == "ENVIRONMENT_UNAVAILABLE"
    dimensions = outcome["delivery_dimensions"]
    assert dimensions["scope_coverage_status"] == "PARTIAL"
    assert dimensions["execution_status"] == "PARTIAL"
    assert outcome["scope_summary"]["declared_scope_mapping_ratio"] < 1.0


def test_v134_auditor_omission_still_forces_none():
    params = _v134_inputs(dispositions=["AUDITOR_OMISSION"])
    params["gate_results"]["request_digest"] = contracts.sha256_json(params["request"])
    outcome = gates.evaluate_run(**params)
    assert outcome["runtime_evidence_level"] == "NONE"
    assert outcome["unverified_paths"][0]["reason_code"] == "AUDITOR_OMISSION"


def test_v134_high_risk_gap_blocks_risk_dimension():
    params = _v134_inputs(dispositions=["NATIVE_INTERACTION_UNAVAILABLE"], risk=True)
    params["gate_results"]["request_digest"] = contracts.sha256_json(params["request"])
    outcome = gates.evaluate_run(**params)
    assert outcome["delivery_dimensions"]["risk_coverage_status"] == "UNVERIFIED"
    assert outcome["status"] != "COMPLETE"


def test_v134_pass_records_get_complete_scope_dimension():
    params = _v134_inputs(dispositions=[])
    params["gate_results"]["request_digest"] = contracts.sha256_json(params["request"])
    outcome = gates.evaluate_run(**params)
    assert outcome["status"] == "COMPLETE"
    assert outcome["delivery_dimensions"]["scope_coverage_status"] == "COMPLETE"
    assert outcome["delivery_dimensions"]["evidence_integrity_status"] == "PASS"
