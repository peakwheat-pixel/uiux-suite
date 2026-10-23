"""Gate computation and finalize (V1.3.3).

Design rules:
- G0–G5 are input gate results; G6 is derived here and never read as an input.
- All state is computed from evidence, tool logs, coverage records and policy.
- WARN_REVIEW_REQUIRED is only discharged by a valid warn review record.
- Mock/Offscreen evidence can never satisfy a NATIVE_APP/OS_INTEGRATION requirement.
- COMPLETE is a combination of mandatory gates, evidence availability, coverage,
  L4 design review and (when required) verified review isolation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import contracts, evidence, policy
from .enums import RANKED_ENUMS, rank

GATES = ("G0", "G1", "G2", "G3", "G4", "G5")
RUNTIME_KINDS = {"test_log", "tool_log", "screenshot", "coverage_matrix"}
REVIEW_ONLY_STATES = {"PASS", "WARN_REVIEW_REQUIRED", "UNVERIFIED"}
WARN_DISPOSITIONS = {"FIXED", "ACCEPTED_RISK", "NOT_APPLICABLE"}


class RunEvaluation:
    def __init__(self, request: dict[str, Any], now: datetime):
        self.request = request
        self.mode = request["mode"]
        self.now = now
        self.facts = policy.facts_from_request(request)
        self.resolved = policy.resolve_mode_gates(self.mode, self.facts)
        self.policy = policy.load_mode_gate_policy()
        self.reasons: list[dict[str, str]] = []
        self.gate_notes: dict[str, list[str]] = {gate: [] for gate in GATES}

    def add(self, gate: str, code: str, detail: str) -> None:
        self.reasons.append({"gate": gate, "code": code, "detail": detail})
        self.gate_notes.setdefault(gate, []).append(code)


def _parse_time(value: str | None) -> datetime | None:
    return evidence.parse_time(value)


def _warn_review_problems(review: dict[str, Any], now: datetime) -> list[str]:
    problems: list[str] = []
    if review.get("disposition") not in WARN_DISPOSITIONS:
        problems.append("WARN_REVIEW_INVALID")
    expires = _parse_time(review.get("expires_at"))
    if expires is None or expires <= now:
        problems.append("WARN_REVIEW_INVALID")
    disposition = review.get("disposition")
    source = review.get("reviewer_source")
    if disposition in ("ACCEPTED_RISK", "NOT_APPLICABLE") and source == "selftest":
        problems.append("WARN_REVIEW_INVALID")
    if disposition == "FIXED" and not review.get("evidence_refs"):
        problems.append("WARN_REVIEW_INVALID")
    return problems


def _warn_reviews_by_gate(warn_reviews: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for review in warn_reviews:
        out.setdefault(review.get("gate"), review)
    return out


def _design_review_status(
    request: dict[str, Any],
    design_review: dict[str, Any] | None,
    independent_required: bool,
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
    if independent_required:
        if reviewer.get("source") not in ("independent_agent", "external_system", "human_expert"):
            run.add("G6", "REVIEW_NOT_INDEPENDENT", "L4 reviewer is not independent")
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
    isolation_ok = isolation in ("ISOLATED_SESSION", "INDEPENDENT_AGENT")
    if not isolation_ok:
        if required:
            run.add("G6", "REVIEW_NOT_INDEPENDENT", "attestation isolation level is not sufficient")
        return "INDEPENDENCE_UNVERIFIED", isolation

    if not attestation.get("source_unchanged"):
        run.add("G6", "SOURCE_CHANGED_DURING_REVIEW", "reviewed source changed")
        return "INDEPENDENCE_UNVERIFIED", isolation

    reviewed_head = str(attestation.get("reviewed_head"))
    if reviewed_head != str(fingerprint.get("value")):
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


def _aggregate_runtime_level(records: list[dict[str, Any]]) -> str:
    levels = []
    for record in records:
        if record.get("test_state") == "NOT_APPLICABLE":
            continue
        if record.get("test_state") == "PASS":
            levels.append(record.get("observed_runtime_level", "NONE"))
        else:
            levels.append("NONE")
    if not levels:
        return "NONE"
    return min(levels, key=lambda level: rank("RuntimeEvidenceLevel", level))


def evaluate_run(
    request: dict[str, Any],
    gate_results: dict[str, Any],
    coverage: dict[str, Any],
    manifest: dict[str, Any],
    tool_logs: list[dict[str, Any]],
    design_review: dict[str, Any] | None = None,
    review_attestation: dict[str, Any] | None = None,
    warn_reviews: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    run = RunEvaluation(request, now)
    manifest_index = evidence.index_items(manifest)
    manifest_digest = evidence.manifest_digest(manifest)
    fingerprint = gate_results.get("source_fingerprint", request.get("source_fingerprint"))

    for problem in evidence.semantic_problems(manifest):
        run.add("G0", "EVIDENCE_MANIFEST_INVALID", problem)

    logs_by_probe: dict[str, dict[str, Any]] = {}
    for log in tool_logs:
        logs_by_probe.setdefault(log.get("probe_id"), log)

    gate_effective_pass: dict[str, bool] = {gate: False for gate in GATES}
    gate_states: dict[str, str] = {}

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

        if expected == "MANDATORY":
            if state == "PASS":
                gate_effective_pass[gate] = True
            elif state == "WARN_REVIEW_REQUIRED":
                pass  # discharged below
            elif state in ("BLOCKED", "FAIL", "UNVERIFIED"):
                code = {
                    "BLOCKED": "ENVIRONMENT_UNAVAILABLE",
                    "FAIL": "GATE_STATE_INVALID",
                    "UNVERIFIED": "MISSING_EVIDENCE",
                }[state]
                run.add(gate, code, f"mandatory gate {gate} is {state}")
        elif expected == "REVIEW_ONLY":
            if state not in REVIEW_ONLY_STATES:
                run.add(gate, "GATE_STATE_INVALID", f"review-only gate {gate} has state {state}")
            elif state in ("PASS", "WARN_REVIEW_REQUIRED"):
                gate_effective_pass[gate] = True

        if gate == "G5":
            required_level = policy.gate_min_level(run.mode, "G5", run.facts, run.policy)
            observed_level = gr.get("observed_runtime_level", "NONE")
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
        problems = _warn_review_problems(review, now)
        if problems:
            for code in problems:
                run.add(gate, code, f"warn review for {gate} is invalid")
            continue
        if run.resolved[gate] == "MANDATORY":
            gate_effective_pass[gate] = True

    # Tool log consistency and layer spoof detection.
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

    # Coverage matrix.
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
        for evidence_id in record.get("evidence_refs", []):
            if evidence_id not in manifest_index:
                run.add("G6", "MISSING_EVIDENCE", f"coverage record references unknown evidence {evidence_id}")
    for target in request["runtime_targets"]:
        covered = any(
            record.get("test_state") == "PASS"
            and rank("RuntimeEvidenceLevel", record.get("observed_runtime_level", "NONE"))
            >= rank("RuntimeEvidenceLevel", target)
            for record in records
        )
        if not covered:
            run.add("G6", "RUNTIME_TARGET_NOT_COVERED", f"requested target {target} has no PASS coverage")

    aggregate_level = _aggregate_runtime_level(records)
    g5_required = policy.gate_min_level(run.mode, "G5", run.facts, run.policy)
    if rank("RuntimeEvidenceLevel", aggregate_level) < rank("RuntimeEvidenceLevel", g5_required):
        run.add("G6", "RUNTIME_LEVEL_BELOW_REQUIRED", f"aggregate {aggregate_level} < required {g5_required}")

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
    design_status = _design_review_status(request, design_review, independent_required, run)
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
        reason["code"] in {"RUNTIME_TARGET_NOT_COVERED", "RUNTIME_LEVEL_BELOW_REQUIRED", "SOURCE_FINGERPRINT_MISMATCH"}
        for reason in run.reasons
    )
    design_ok = design_status in ("NOT_REQUIRED", "PASS")
    review_ok = independent_status in ("NOT_APPLICABLE", "INDEPENDENT_REVIEW_PASS")
    if independent_required and independent_status != "INDEPENDENT_REVIEW_PASS":
        review_ok = False

    blocked = any(reason["code"] in {"ENVIRONMENT_UNAVAILABLE", "PERMISSION_DENIED"} for reason in run.reasons)
    failed = any(
        reason["code"] == "GATE_STATE_INVALID" and "mandatory gate" in reason["detail"]
        for reason in run.reasons
    )

    complete = (
        mandatory_ok and evidence_ok and coverage_ok and design_ok and review_ok
        and not run.reasons
        and not unverified_paths
    )
    if blocked:
        status = "BLOCKED"
    elif failed and not mandatory_ok:
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

    return {
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
        "resolved_gates": run.resolved,
        "gate_effective_pass": gate_effective_pass,
        "required_gates": policy.required_gates(run.mode, run.facts, run.policy),
    }
