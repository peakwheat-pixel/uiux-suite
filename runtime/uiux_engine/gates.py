"""Gate computation and finalize (V1.3.4, dual-contract).

Design rules:
- G0–G5 are input gate results; G6 is derived here and never read as an input.
- All state is computed from evidence, tool logs, coverage records and policy.
- WARN_REVIEW_REQUIRED is only discharged by a schema-valid review bound to the
  frozen source fingerprint.
- Mock/Offscreen evidence can never satisfy a NATIVE_APP/OS_INTEGRATION
  requirement: coverage records are cross-checked against manifest provenance
  and tool-log execution levels.
- COMPLETE is a combination of mandatory gates, evidence availability, coverage,
  L4 design review and (when required) verified review isolation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import contracts, evidence, policy
from .enums import rank

GATES = ("G0", "G1", "G2", "G3", "G4", "G5")
RUNTIME_KINDS = {"test_log", "tool_log", "screenshot", "coverage_matrix"}


class RunEvaluation:
    def __init__(
        self,
        request: dict[str, Any],
        now: datetime,
        schema_version: str | None = None,
    ):
        self.request = request
        self.mode = request["mode"]
        self.now = now
        self.schema_version = (
            schema_version
            or request.get("schema_version")
            or contracts.CURRENT_SCHEMA_VERSION
        )
        self.facts = policy.facts_from_request(request, self.schema_version)
        self.resolved = policy.resolve_mode_gates(self.mode, self.facts, version=self.schema_version)
        self.policy = policy.load_mode_gate_policy(self.schema_version)
        self.reasons: list[dict[str, str]] = []
        self.gate_notes: dict[str, list[str]] = {gate: [] for gate in GATES}

    def add(self, gate: str, code: str, detail: str) -> None:
        self.reasons.append({"gate": gate, "code": code, "detail": detail})
        self.gate_notes.setdefault(gate, []).append(code)


def _warn_review_problems(
    review: dict[str, Any],
    now: datetime,
    fingerprint: dict[str, Any],
    manifest_index: dict[str, dict[str, Any]],
    schema_version: str = contracts.CURRENT_SCHEMA_VERSION,
) -> list[str]:
    problems: list[str] = []
    problems.extend(
        "WARN_REVIEW_INVALID"
        for _ in contracts.fragment_errors("common", "warn_review", review, version=schema_version)
    )
    if problems:
        return problems
    expires = evidence.parse_time(review.get("expires_at"))
    if expires is None or expires <= now:
        problems.append("WARN_REVIEW_INVALID")
    disposition = review.get("disposition")
    source = review.get("reviewer_source")
    if disposition in ("ACCEPTED_RISK", "NOT_APPLICABLE") and source == "selftest":
        problems.append("WARN_REVIEW_INVALID")
    if disposition in ("FIXED", "REJECTED"):
        refs = review.get("evidence_refs") or []
        if not refs:
            problems.append("WARN_REVIEW_INVALID")
        for evidence_id in refs:
            item = manifest_index.get(evidence_id)
            if item is None:
                problems.append("MISSING_EVIDENCE")
            elif evidence.effective_status(item, now) != "AVAILABLE":
                problems.append("WARN_REVIEW_INVALID")
    if str(review.get("reviewed_head")) != str(fingerprint.get("value")):
        problems.append("REVIEWED_HEAD_MISMATCH")
    return problems


def _warn_reviews_by_gate(warn_reviews: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for review in warn_reviews:
        out.setdefault(review.get("gate"), review)
    return out


def _design_review_status(
    request: dict[str, Any],
    design_review: dict[str, Any] | None,
    l4_independent: bool,
    run: RunEvaluation,
) -> str:
    if not policy.l4_required(run.mode, run.policy):
        return "NOT_REQUIRED"
    if design_review is None:
        run.add("G6", "DESIGN_REVIEW_MISSING", "L4 design review required but absent")
        return "MISSING"
    schema_errors = contracts.validation_errors("design-review", design_review)
    if schema_errors:
        run.add("G6", "DESIGN_REVIEW_INVALID", "; ".join(schema_errors[:3]))
        return "INCOMPLETE"
    dimensions = design_review.get("dimensions", [])
    dimension_ids = [item.get("dimension_id") for item in dimensions]
    if len(set(dimension_ids)) < 10 or set(dimension_ids) != set(
        run.policy["design_review_policy"]["required_dimensions"]
    ):
        run.add("G6", "DESIGN_REVIEW_INSUFFICIENT", "not all 10 required dimensions are present exactly once")
        return "INCOMPLETE"
    reviewer = design_review.get("reviewer", {})
    if l4_independent:
        if reviewer.get("source") not in ("independent_agent", "external_system", "human_expert"):
            run.add("G6", "REVIEW_NOT_INDEPENDENT", "production-code L4 reviewer is not independent")
            return "INCOMPLETE"
        if not reviewer.get("independence_proof_ref"):
            run.add("G6", "REVIEW_SOURCE_MISSING", "L4 reviewer lacks independence proof")
            return "INCOMPLETE"
    verdict = design_review.get("overall_verdict")
    if verdict == "PASS":
        return "PASS"
    if verdict == "FAIL":
        run.add("G6", "DESIGN_REVIEW_INSUFFICIENT", "L4 review verdict is FAIL")
        return "FAIL"
    return "UNVERIFIED"


def _review_status(
    request: dict[str, Any],
    attestation: dict[str, Any] | None,
    manifest_digest: str,
    fingerprint: dict[str, Any],
    run: RunEvaluation,
) -> tuple[str, str]:
    """Return (independent_review_status, review_isolation_level)."""
    required = policy.independent_review_required(run.mode, request, run.policy)
    if attestation is None:
        if required:
            run.add("G6", "REVIEW_SOURCE_MISSING", "independent review required but no attestation")
            return "UNVERIFIED", "SELFTEST"
        return "NOT_APPLICABLE", "SELFTEST"

    schema_errors = contracts.validation_errors("review-attestation", attestation)
    if schema_errors:
        run.add("G6", "REVIEW_ATTESTATION_INVALID", "; ".join(schema_errors[:3]))
        return "UNVERIFIED", "UNVERIFIED"

    isolation = attestation.get("isolation_level")
    if isolation not in ("ISOLATED_SESSION", "INDEPENDENT_AGENT"):
        if required:
            run.add("G6", "REVIEW_NOT_INDEPENDENT", "attestation isolation level is not sufficient")
        return "INDEPENDENCE_UNVERIFIED", isolation

    if not attestation.get("source_unchanged"):
        run.add("G6", "SOURCE_CHANGED_DURING_REVIEW", "reviewed source changed")
        return "INDEPENDENCE_UNVERIFIED", isolation

    if str(attestation.get("reviewed_head")) != str(fingerprint.get("value")):
        run.add("G6", "REVIEWED_HEAD_MISMATCH", "reviewed_head does not match frozen source fingerprint")
        return "INDEPENDENCE_UNVERIFIED", isolation

    if attestation.get("evidence_manifest_hash") != manifest_digest:
        run.add("G6", "INVALID_EVIDENCE_HASH", "attestation evidence_manifest_hash mismatch")
        return "INDEPENDENCE_UNVERIFIED", isolation

    verdict = attestation.get("verdict")
    if verdict != "PASS":
        run.add("G6", "REVIEW_SOURCE_UNVERIFIED", f"review verdict is {verdict}")
        return "INDEPENDENT_REVIEW_FAIL" if verdict == "FAIL" else "UNVERIFIED", isolation

    trust = (attestation.get("review_origin") or {}).get("trust_source")
    if isolation == "INDEPENDENT_AGENT":
        if trust not in ("host_verified", "external_system"):
            run.add("G6", "REVIEW_SOURCE_UNVERIFIED", "independent agent review lacks verified trust source")
            return "INDEPENDENCE_UNVERIFIED", isolation
        return "INDEPENDENT_REVIEW_PASS", "INDEPENDENT_AGENT"
    return "INDEPENDENCE_UNVERIFIED", "ISOLATED_SESSION"


# V1.3.4: dispositions that describe a *capability/environment* limit rather
# than a product or audit failure. They are excluded from the runtime-level
# aggregate but always recorded in unverified_paths with their reason code.
EXCLUDED_DISPOSITIONS = {
    "ENVIRONMENT_UNAVAILABLE",
    "NATIVE_INTERACTION_UNAVAILABLE",
    "TOOL_UNAVAILABLE",
    "FIXTURE_INVALID",
    "NOT_APPLICABLE",
}
NON_EXCLUDED_DISPOSITIONS = {
    "AUDITOR_OMISSION",
    "PRODUCT_FAILURE",
    "EVIDENCE_MISSING",
    "INDEPENDENCE_UNVERIFIED",
}


def _aggregate_runtime_level(
    records: list[dict[str, Any]],
    schema_version: str = contracts.CURRENT_SCHEMA_VERSION,
) -> str:
    levels = []
    for record in records:
        state = record.get("test_state")
        if state == "NOT_APPLICABLE":
            continue
        if schema_version in ("1.3.4", "1.3.5"):
            disposition = record.get("disposition")
            if state == "PASS":
                levels.append(record.get("observed_runtime_level", "NONE"))
            elif disposition in EXCLUDED_DISPOSITIONS:
                # scoped capability/environment limit: excluded from the
                # aggregate but still tracked as an unverified path
                continue
            else:
                levels.append("NONE")
            continue
        # V1.3.3 legacy semantics: any non-PASS record forces NONE
        if state == "PASS":
            levels.append(record.get("observed_runtime_level", "NONE"))
        else:
            levels.append("NONE")
    if not levels:
        return "NONE"
    return min(levels, key=lambda level: rank("RuntimeEvidenceLevel", level))


def _scope_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    def is_pass(record: dict[str, Any]) -> bool:
        return record.get("test_state") == "PASS"

    total = len(records)
    passed = sum(1 for r in records if is_pass(r))
    unverified = sum(1 for r in records if r.get("test_state") not in ("PASS", "NOT_APPLICABLE"))
    excluded = sum(1 for r in records if r.get("disposition") in EXCLUDED_DISPOSITIONS)
    high_risk = [r for r in records if r.get("risk_ref")]
    high_risk_passed = sum(1 for r in high_risk if is_pass(r))
    return {
        "inventory_total": total,
        "mapped_total": total,
        "executed_total": total,
        "verified_total": passed,
        "unverified_total": unverified,
        "unreachable_total": excluded,
        "excluded_total": sum(1 for r in records if r.get("test_state") == "NOT_APPLICABLE"),
        "high_risk_total": len(high_risk),
        "high_risk_verified_total": high_risk_passed,
        "declared_scope_mapping_ratio": round(passed / total, 4) if total else 0.0,
    }


def _risk_coverage_status(records: list[dict[str, Any]]) -> str:
    high_risk = [r for r in records if r.get("risk_ref")]
    if not high_risk:
        return "NOT_APPLICABLE"
    for record in high_risk:
        disposition = record.get("disposition")
        if record.get("test_state") == "PASS":
            continue
        if disposition in EXCLUDED_DISPOSITIONS:
            return "UNVERIFIED"
        return "BLOCKED"
    return "PASS"


def _delivery_dimensions(
    *,
    status: str,
    delivery: str,
    independent_status: str,
    evidence_ok: bool,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    has_scoped_exclusions = any(
        r.get("disposition") in EXCLUDED_DISPOSITIONS and r.get("test_state") != "PASS"
        for r in records
    )
    if not records:
        scope_status = "UNKNOWN"
    elif all(r.get("test_state") == "PASS" or r.get("test_state") == "NOT_APPLICABLE" for r in records):
        scope_status = "COMPLETE"
    else:
        scope_status = "PARTIAL"
    return {
        "execution_status": status,
        "scope_coverage_status": scope_status,
        "evidence_integrity_status": "PASS" if evidence_ok else "FAIL",
        "risk_coverage_status": _risk_coverage_status(records),
        "independence_status": independent_status,
        "delivery_status": delivery,
        "notes": (
            "scoped exclusions present; delivery is a scoped partial, not a full-product PASS"
            if has_scoped_exclusions and status == "PARTIAL"
            else "derived by the V1.3.4 engine from evidence and coverage"
        ),
    }



def _max_evidence_level(refs: list[dict[str, Any]]) -> str:
    levels = [ref.get("evidence_level", "NONE") for ref in refs]
    if not levels:
        return "NONE"
    return max(levels, key=lambda level: rank("RuntimeEvidenceLevel", level))


def _coverage_layer_problems(
    records: list[dict[str, Any]],
    manifest_index: dict[str, dict[str, Any]],
    logs_by_probe: dict[str, dict[str, Any]],
    now: datetime,
) -> list[tuple[str, str]]:
    """Cross-check coverage claims against manifest provenance and tool logs."""
    out: list[tuple[str, str]] = []
    status_codes = {
        "EXPIRED": "EVIDENCE_EXPIRED",
        "INVALID_HASH": "INVALID_EVIDENCE_HASH",
        "QUARANTINED": "EVIDENCE_QUARANTINED",
        "SOURCE_EVIDENCE_UNAVAILABLE": "EVIDENCE_SOURCE_UNAVAILABLE",
        "REDACTED_ONLY": "EVIDENCE_SOURCE_UNAVAILABLE",
    }
    for record in records:
        if record.get("test_state") == "NOT_APPLICABLE":
            continue
        observed = record.get("observed_runtime_level", "NONE")
        probe_id = record.get("probe_id")
        matching_origin = False
        for evidence_id in record.get("evidence_refs", []):
            item = manifest_index.get(evidence_id)
            if item is None:
                out.append(("MISSING_EVIDENCE", f"coverage references unknown evidence {evidence_id}"))
                continue
            status = evidence.effective_status(item, now)
            if status != "AVAILABLE":
                out.append((status_codes.get(status, "MISSING_EVIDENCE"), f"coverage evidence {evidence_id} is {status}"))
                continue
            provenance = item.get("provenance") or {}
            if provenance.get("probe_id") != probe_id:
                out.append(("PROBE_ID_MISSING", f"coverage probe {probe_id} differs from evidence provenance"))
                continue
            if rank("RuntimeEvidenceLevel", provenance.get("execution_level", "NONE")) >= rank(
                "RuntimeEvidenceLevel", observed
            ):
                matching_origin = True
        if observed != "NONE" and not matching_origin:
            out.append(
                ("LAYER_SPOOF_OR_MISSING", f"coverage claims {observed} without matching evidence provenance")
            )
        if rank("RuntimeEvidenceLevel", observed) >= rank("RuntimeEvidenceLevel", "NATIVE_APP"):
            log = logs_by_probe.get(probe_id)
            if log is None:
                out.append(("TOOL_LOG_MISSING", f"coverage probe {probe_id} has no tool log"))
            else:
                if log.get("exit_code") != 0:
                    out.append(("TOOL_EXIT_NONZERO", f"tool log {log.get('log_id')} exit {log.get('exit_code')}"))
                if rank("RuntimeEvidenceLevel", log.get("execution_level", "NONE")) < rank(
                    "RuntimeEvidenceLevel", observed
                ):
                    out.append(
                        (
                            "LAYER_SPOOF_OR_MISSING",
                            f"coverage claims {observed} but tool log is {log.get('execution_level')}",
                        )
                    )
    return out


def evaluate_run(
    request: dict[str, Any],
    gate_results: dict[str, Any],
    coverage: dict[str, Any],
    manifest: dict[str, Any],
    tool_logs: list[dict[str, Any]],
    design_review: dict[str, Any] | None = None,
    review_attestation: dict[str, Any] | None = None,
    warn_reviews: list[dict[str, Any]] | None = None,
    repair_cycles: int = 0,
    now: datetime | None = None,
    schema_version: str | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    run = RunEvaluation(request, now, schema_version=schema_version)

    # V1.3.4: fail closed on mixed or missing contract versions across inputs.
    consistency = contracts.version_consistency_errors(
        run.schema_version,
        {
            "request": request,
            "gate-results": gate_results,
            "coverage-matrix": coverage,
            "evidence-manifest": manifest,
            "design-review": design_review,
            "review-attestation": review_attestation,
            "tool-logs": tool_logs,
        },
    )
    for problem in consistency:
        run.add("G0", "SCHEMA_VERSION_MISMATCH", problem)

    manifest_index = evidence.index_items(manifest)
    manifest_digest = evidence.manifest_digest(manifest)
    fingerprint = gate_results.get("source_fingerprint", request.get("source_fingerprint"))

    if gate_results.get("request_digest"):
        if gate_results["request_digest"] != contracts.sha256_json(request):
            run.add("G6", "REQUEST_DIGEST_MISMATCH", "gate-results request_digest differs from current request")

    for problem in evidence.semantic_problems(manifest):
        run.add("G0", "EVIDENCE_MANIFEST_INVALID", problem)

    logs_by_probe: dict[str, dict[str, Any]] = {}
    for log in tool_logs:
        logs_by_probe.setdefault(log.get("probe_id"), log)

    review_only_states = set(run.policy["complete_policy"]["review_only_gate_acceptable_states"])
    gate_effective_pass: dict[str, bool] = {gate: False for gate in GATES}
    gate_states: dict[str, str] = {}
    mandatory_failed = False
    review_only_failed = False

    for gate in GATES:
        gr = gate_results["gates"][gate]
        expected = run.resolved[gate]
        state = gr["state"]
        gate_states[gate] = state
        observed_applicability = gr["applicability"]

        if expected == "NOT_APPLICABLE":
            if state != "NOT_APPLICABLE" or observed_applicability != "NOT_APPLICABLE":
                run.add(gate, "GATE_STATE_INVALID", "gate should be NOT_APPLICABLE for this mode")
            continue

        if observed_applicability == "NOT_APPLICABLE":
            run.add(gate, "GATE_NOT_APPLICABLE_REQUIRED", "mandatory/review gate was marked NOT_APPLICABLE")
            continue

        require_available = state in ("PASS", "WARN_REVIEW_REQUIRED")
        for code in evidence.check_gate_evidence(gr, manifest_index, now, require_available):
            run.add(gate, code, f"evidence check failed for gate {gate}")

        observed_level = gr.get("observed_runtime_level", "NONE")
        if observed_level and observed_level != "NONE":
            max_level = _max_evidence_level(gr.get("evidence_refs", []))
            if rank("RuntimeEvidenceLevel", observed_level) > rank("RuntimeEvidenceLevel", max_level):
                run.add(
                    gate,
                    "LAYER_SPOOF_OR_MISSING",
                    f"gate {gate} claims {observed_level} but evidence max is {max_level}",
                )

        if expected == "MANDATORY":
            if state == "PASS":
                gate_effective_pass[gate] = True
            elif state == "WARN_REVIEW_REQUIRED":
                pass  # discharged below
            elif state == "FAIL":
                mandatory_failed = True
                run.add(gate, "GATE_STATE_INVALID", f"mandatory gate {gate} is FAIL")
            elif state == "BLOCKED":
                run.add(gate, "ENVIRONMENT_UNAVAILABLE", f"mandatory gate {gate} is BLOCKED")
            elif state == "UNVERIFIED":
                run.add(gate, "MISSING_EVIDENCE", f"mandatory gate {gate} is UNVERIFIED")
        elif expected == "REVIEW_ONLY":
            if state == "FAIL":
                review_only_failed = True
                run.add(gate, "GATE_STATE_INVALID", f"review-only gate {gate} is FAIL")
            elif state not in review_only_states:
                run.add(gate, "GATE_STATE_INVALID", f"review-only gate {gate} has state {state}")
            elif state in ("PASS", "WARN_REVIEW_REQUIRED"):
                gate_effective_pass[gate] = True

        if gate == "G5":
            required_level = policy.gate_min_level(run.mode, "G5", run.facts, run.policy)
            if rank("RuntimeEvidenceLevel", observed_level) < rank("RuntimeEvidenceLevel", required_level):
                run.add(gate, "RUNTIME_LEVEL_BELOW_REQUIRED", f"G5 observed {observed_level} < required {required_level}")

    reviews = _warn_reviews_by_gate(warn_reviews or [])
    for gate in GATES:
        if gate_states.get(gate) != "WARN_REVIEW_REQUIRED":
            continue
        review = gate_results["gates"][gate].get("warn_review") or reviews.get(gate)
        if review is None:
            run.add(gate, "WARN_REVIEW_MISSING", "WARN_REVIEW_REQUIRED has no disposition record")
            continue
        if review.get("gate") not in (None, gate):
            run.add(gate, "WARN_REVIEW_INVALID", f"warn review gate mismatch: {review.get('gate')}")
            continue
        problems = _warn_review_problems(review, now, fingerprint, manifest_index, run.schema_version)
        if problems:
            for code in problems:
                run.add(gate, code, f"warn review for {gate} is invalid")
            continue
        if run.resolved[gate] == "MANDATORY":
            gate_effective_pass[gate] = True

    # Tool log consistency and layer spoof detection for gate evidence.
    for gate in GATES:
        gr = gate_results["gates"][gate]
        if gr["state"] not in ("PASS", "WARN_REVIEW_REQUIRED"):
            continue
        for ref in gr.get("evidence_refs", []):
            if ref.get("kind") not in RUNTIME_KINDS:
                continue
            log = logs_by_probe.get(ref.get("probe_id"))
            if log is None:
                run.add(gate, "TOOL_LOG_MISSING", f"no tool log for probe {ref.get('probe_id')}")
                continue
            if log.get("exit_code") != 0:
                run.add(gate, "TOOL_EXIT_NONZERO", f"tool log {log.get('log_id')} exit {log.get('exit_code')}")
            if rank("RuntimeEvidenceLevel", log.get("execution_level", "NONE")) < rank(
                "RuntimeEvidenceLevel", ref.get("evidence_level", "NONE")
            ):
                run.add(gate, "LAYER_SPOOF_OR_MISSING", "evidence level exceeds tool execution level")

    # Coverage matrix: required levels, target coverage, and provenance bindings.
    records = coverage.get("records", [])
    if coverage.get("source_fingerprint") != gate_results.get("source_fingerprint"):
        run.add("G6", "SOURCE_FINGERPRINT_MISMATCH", "coverage source_fingerprint differs from gate-results")
    for record in records:
        if record.get("test_state") != "PASS":
            continue
        if rank("RuntimeEvidenceLevel", record.get("observed_runtime_level", "NONE")) < rank(
            "RuntimeEvidenceLevel", record.get("required_runtime_level", "NONE")
        ):
            run.add("G6", "RUNTIME_LEVEL_BELOW_REQUIRED", f"record {record.get('scenario_id')} below required level")
    for code, detail in _coverage_layer_problems(records, manifest_index, logs_by_probe, now):
        run.add("G6", code, detail)
    for target in request["runtime_targets"]:
        covered = any(
            record.get("test_state") == "PASS"
            and rank("RuntimeEvidenceLevel", record.get("observed_runtime_level", "NONE"))
            >= rank("RuntimeEvidenceLevel", target)
            for record in records
        )
        if not covered:
            run.add("G6", "RUNTIME_TARGET_NOT_COVERED", f"requested target {target} has no PASS coverage")

    aggregate_level = _aggregate_runtime_level(records, run.schema_version)
    g5_required = policy.gate_min_level(run.mode, "G5", run.facts, run.policy)
    if rank("RuntimeEvidenceLevel", aggregate_level) < rank("RuntimeEvidenceLevel", g5_required):
        run.add("G6", "RUNTIME_LEVEL_BELOW_REQUIRED", f"aggregate {aggregate_level} < required {g5_required}")

    if run.schema_version in ("1.3.4", "1.3.5"):
        unverified_paths = [
            {
                "task_id": record.get("task_id"),
                "scenario_id": record.get("scenario_id"),
                "required_runtime_level": record.get("required_runtime_level", "NONE"),
                "reason_code": record.get("disposition") or "UNVERIFIED_PATH",
                "detail": (
                    f"test_state={record.get('test_state')}"
                    + (f"; scope_ref={record.get('scope_ref')}" if record.get("scope_ref") else "")
                    + (f"; risk_ref={record.get('risk_ref')}" if record.get("risk_ref") else "")
                ),
            }
            for record in records
            if record.get("test_state") not in ("PASS", "NOT_APPLICABLE")
        ]
    else:
        unverified_paths = [
            {
                "task_id": record.get("task_id"),
                "scenario_id": record.get("scenario_id"),
                "required_runtime_level": record.get("required_runtime_level", "NONE"),
                "reason_code": "UNVERIFIED_PATH",
                "detail": f"test_state={record.get('test_state')}",
            }
            for record in records
            if record.get("test_state") != "PASS" and record.get("test_state") != "NOT_APPLICABLE"
        ]

    independent_required = policy.independent_review_required(run.mode, request, run.policy)
    l4_independent = policy.l4_independent_required(run.mode, request, run.policy)
    design_status = _design_review_status(request, design_review, l4_independent, run)
    independent_status, isolation = _review_status(
        request, review_attestation, manifest_digest, fingerprint, run
    )

    mandatory_ok = all(gate_effective_pass[gate] for gate in GATES if run.resolved[gate] == "MANDATORY")
    evidence_ok = not any(
        reason["code"]
        in {
            "MISSING_EVIDENCE", "INVALID_EVIDENCE_HASH", "EVIDENCE_EXPIRED",
            "EVIDENCE_SOURCE_UNAVAILABLE", "EVIDENCE_QUARANTINED", "PROBE_ID_MISSING",
            "TOOL_LOG_MISSING", "TOOL_EXIT_NONZERO", "LAYER_SPOOF_OR_MISSING",
        }
        for reason in run.reasons
    )
    coverage_ok = not any(
        reason["code"]
        in {"RUNTIME_TARGET_NOT_COVERED", "RUNTIME_LEVEL_BELOW_REQUIRED", "SOURCE_FINGERPRINT_MISMATCH", "REQUEST_DIGEST_MISMATCH"}
        for reason in run.reasons
    )
    design_ok = design_status in ("NOT_REQUIRED", "PASS")
    review_ok = (not independent_required) or independent_status == "INDEPENDENT_REVIEW_PASS"

    blocked = any(reason["code"] in {"ENVIRONMENT_UNAVAILABLE", "PERMISSION_DENIED"} for reason in run.reasons)

    complete = (
        mandatory_ok and evidence_ok and coverage_ok and design_ok and review_ok
        and not run.reasons
        and not unverified_paths
    )
    if blocked:
        status = "BLOCKED"
    elif mandatory_failed or review_only_failed or design_status == "FAIL":
        status = "FAILED"
    elif complete:
        status = "COMPLETE"
    else:
        status = "PARTIAL"

    if status == "COMPLETE":
        if independent_status == "INDEPENDENT_REVIEW_PASS":
            delivery = "INDEPENDENT_VERIFIED"
        elif isolation == "ISOLATED_SESSION":
            delivery = "ISOLATED_REVIEW_VERIFIED"
        else:
            delivery = "SELFTEST_VERIFIED"
    elif status == "PARTIAL":
        delivery = "PARTIAL_VERIFIED"
    else:
        delivery = "NOT_VERIFIED"

    g6_checks: list[dict[str, str]] = []
    for gate in GATES:
        expected = run.resolved[gate]
        state = gate_states[gate]
        g6_checks.append(
            {
                "id": f"gate:{gate}",
                "state": state if state in ("PASS", "FAIL", "BLOCKED", "UNVERIFIED", "NOT_APPLICABLE") else "FAIL",
                "detail": f"applicability={expected} state={state}",
            }
        )
    g6_checks.append({"id": "coverage:targets", "state": "PASS" if coverage_ok else "FAIL", "detail": "runtime target coverage"})
    g6_checks.append({"id": "evidence:available", "state": "PASS" if evidence_ok else "FAIL", "detail": "evidence availability and integrity"})
    g6_checks.append({"id": "design:l4", "state": "PASS" if design_ok else "FAIL", "detail": f"design_review_status={design_status}"})
    g6_checks.append({"id": "review:isolation", "state": "PASS" if review_ok else "FAIL", "detail": f"independent_review_status={independent_status}"})
    g6_checks.append({"id": "source:fingerprint", "state": "PASS" if coverage_ok else "FAIL", "detail": "frozen source fingerprint"})
    if status == "COMPLETE":
        g6_state = "PASS"
    elif status == "BLOCKED":
        g6_state = "BLOCKED"
    elif status == "FAILED":
        g6_state = "FAIL"
    else:
        g6_state = "UNVERIFIED"

    blocking_reasons = list(run.reasons)
    if status != "COMPLETE" and not blocking_reasons:
        blocking_reasons.append(
            {"gate": "G6", "code": "COMPLETE_CONSTRAINT_VIOLATION", "detail": "COMPLETE constraints not satisfied"}
        )

    result = {
        "schema_version": run.schema_version,
        "status": status,
        "delivery_status": delivery,
        "independent_review_status": independent_status,
        "design_review_status": design_status,
        "runtime_evidence_level": aggregate_level,
        "review_isolation_level": isolation,
        "derived_g6": {
            "state": g6_state,
            "checks": g6_checks,
            "computed_at": now.isoformat(),
        },
        "coverage_matrix": records,
        "unverified_paths": unverified_paths,
        "blocking_reasons": blocking_reasons,
        "warn_reviews": list(warn_reviews or []),
        "design_review_ref": "design-review.json" if design_review else None,
        "review_attestation_ref": "review-attestation.json" if review_attestation else None,
        "evidence_manifest_ref": ".uiux/evidence/manifest.json",
        "manifest_digest": manifest_digest,
        "repair_cycles": repair_cycles,
        "resolved_gates": run.resolved,
        "gate_effective_pass": gate_effective_pass,
        "required_gates": policy.required_gates(run.mode, run.facts, run.policy),
    }
    if run.schema_version in ("1.3.4", "1.3.5"):
        result["delivery_dimensions"] = _delivery_dimensions(
            status=status,
            delivery=delivery,
            independent_status=independent_status,
            evidence_ok=evidence_ok,
            records=records,
        )
        result["scope_summary"] = _scope_summary(records)
    return result
