"""UIUX engine CLI (V1.3.3).

Exit codes are part of the contract:
  0   successful validation / COMPLETE result
  2   usage error
  10  schema or semantic validation failure
  11  PARTIAL result
  12  FAILED result
  13  BLOCKED result
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import build_guard, compat, contracts, enums, external, gates, input_policy, integrity, knowledge, modify, policy, rules, safety, snapshot, token_compiler, validation, vault

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_INVALID = 10
EXIT_PARTIAL = 11
EXIT_FAILED = 12
EXIT_BLOCKED = 13
STATUS_EXIT = {
    "COMPLETE": EXIT_OK,
    "PARTIAL": EXIT_PARTIAL,
    "FAILED": EXIT_FAILED,
    "BLOCKED": EXIT_BLOCKED,
}


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _invalid(errors: list[str], context: str = "") -> int:
    _emit({"ok": False, "context": context, "errors": errors})
    return EXIT_INVALID


def _load(path: str) -> Any:
    return contracts.load_json(path)


def _load_list(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    target = Path(path)
    if target.is_dir():
        docs = [_load(str(item)) for item in sorted(target.glob("*.json"))]
    else:
        doc = _load(path)
        docs = doc if isinstance(doc, list) else [doc]
    out: list[dict[str, Any]] = []
    for doc in docs:
        if isinstance(doc, list):
            out.extend(doc)
        else:
            out.append(doc)
    return out


def _parse_now(value: str | None) -> datetime | None:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def cmd_enums(_: argparse.Namespace) -> int:
    _emit(enums.load_enums())
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    if args.schema not in contracts.SCHEMA_FILES:
        _emit({"ok": False, "errors": [f"unknown schema {args.schema!r}"]})
        return EXIT_USAGE
    try:
        instance = _load(args.instance)
    except Exception as exc:  # noqa: BLE001 - report file errors uniformly
        return _invalid([str(exc)], context=args.instance)
    errors.extend(contracts.validation_errors(args.schema, instance))
    if args.schema == "task-request" and not errors:
        for problem in validation.request_semantic_errors(instance):
            errors.append(f"{problem['code']}: {problem['detail']}")
    if errors:
        return _invalid(errors, context=f"schema={args.schema}")
    _emit({"ok": True, "schema": args.schema, "instance": args.instance})
    return EXIT_OK


def cmd_rules(args: argparse.Namespace) -> int:
    try:
        catalog = rules.load_catalog(args.catalog)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="rule catalog")
    problems = rules.semantic_problems(catalog)
    freeze = rules.verify_frozen() if not args.catalog else []
    all_problems = problems + freeze
    payload = {
        "ok": not all_problems,
        "catalog_version": catalog.get("catalog_version"),
        "rules_count": len(catalog.get("rules", [])),
        "sha256": rules.canonical_digest(catalog),
        "frozen": not freeze,
        "errors": all_problems,
    }
    _emit(payload)
    return EXIT_OK if not all_problems else EXIT_INVALID


def cmd_modify(args: argparse.Namespace) -> int:
    try:
        plan = contracts.load_json(args.plan)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="change plan")
    if args.revert:
        result = modify.revert_plan(plan, args.root, args.revert)
        _emit(result)
        return EXIT_OK
    if not args.apply:
        _emit({"ok": True, "dry_run": True, "problems": modify.validate_plan(plan, args.root), "diff": modify.diff_plan(plan, args.root)})
        return EXIT_OK if not modify.validate_plan(plan, args.root) else EXIT_INVALID
    result = modify.apply_plan(plan, args.root, backup_dir=args.backup)
    _emit(result)
    return EXIT_OK if result["ok"] else EXIT_INVALID


def cmd_vault(args: argparse.Namespace) -> int:
    try:
        manifest = contracts.load_json(args.manifest)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="evidence manifest")
    result = vault.verify(manifest, args.root, quarantine_dir=args.quarantine)
    _emit(result)
    return EXIT_OK if result["ok"] else EXIT_INVALID


def cmd_integrity(args: argparse.Namespace) -> int:
    try:
        chain = contracts.load_json(args.chain)
        attestation = contracts.load_json(args.attestation) if args.attestation else {}
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="integrity input")
    result = integrity.verify_report(chain, attestation, args.commit)
    _emit(result)
    return EXIT_OK if result["ok"] else EXIT_INVALID


def cmd_safety(args: argparse.Namespace) -> int:
    try:
        plan = contracts.load_json(args.plan)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="change plan")
    _emit(safety.classify_plan(plan))
    return EXIT_OK


def cmd_compat(args: argparse.Namespace) -> int:
    _emit(compat.degradation_report(args.agents_home))
    return EXIT_OK


def cmd_input_policy(args: argparse.Namespace) -> int:
    result = input_policy.authorize(args.channel, isolated=args.isolated, read_only=args.read_only, explicit=args.explicit)
    _emit(result)
    return EXIT_OK if result["decision"] == "ALLOW" else EXIT_INVALID


def cmd_build_guard(args: argparse.Namespace) -> int:
    result = build_guard.check(args.command, args.root, allow_network=args.allow_network)
    _emit(result)
    return EXIT_OK if result["decision"] == "ALLOW" else EXIT_INVALID


def cmd_knowledge(args: argparse.Namespace) -> int:
    try:
        index = knowledge.load_index(args.index)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="knowledge index")
    result = knowledge.verify(index, args.root)
    _emit(result)
    return EXIT_OK if result["ok"] else EXIT_INVALID


def cmd_tokens(args: argparse.Namespace) -> int:
    try:
        path = token_compiler.compile_tokens(args.format, args.out)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="token compiler")
    _emit({"ok": True, "format": args.format, "out": str(path)})
    return EXIT_OK


def cmd_snapshot(args: argparse.Namespace) -> int:
    if args.diff:
        try:
            before = snapshot.load_snapshot(args.diff[0])
            after = snapshot.load_snapshot(args.diff[1])
        except (OSError, ValueError, KeyError) as exc:
            return _invalid([str(exc)], context="snapshot diff")
        diff = snapshot.diff_snapshots(before, after)
        _emit({"ok": diff["identical"], **diff})
        return EXIT_OK if diff["identical"] else EXIT_PARTIAL
    if not args.root:
        _emit({"ok": False, "errors": ["snapshot requires --root or --diff BEFORE AFTER"]})
        return EXIT_USAGE
    try:
        data = snapshot.build_snapshot(args.root)
        backup = None
        if args.backup:
            backup = str(snapshot.backup_tree(args.root, args.backup))
        if args.out:
            snapshot.write_snapshot(args.root, args.out)
    except (OSError, ValueError) as exc:
        return _invalid([str(exc)], context="snapshot")
    _emit(
        {
            "ok": True,
            "root_name": data["root_name"],
            "file_count": data["file_count"],
            "digest": contracts.sha256_json(data["files"]),
            "out": args.out,
            "backup": backup,
        }
    )
    return EXIT_OK


def cmd_policy(args: argparse.Namespace) -> int:
    if args.request:
        request = _load(args.request)
        facts = policy.facts_from_request(request)
        mode = request["mode"]
    else:
        mode = args.mode
        facts = {
            "mode": mode,
            "deliverable_tier": policy.deliverable_tier(mode),
            "project.has_existing_ui": mode in ("audit", "redesign", "targeted-fix", "verify"),
            "request.read_only_source": mode in ("audit", "design-only", "prototype", "verify"),
            "request.target_scope_nonempty": True,
            "request.execution_policy.require_native_for_production_complete": True,
            "request.evidence_policy.profile": "local_private",
            "runtime_targets": ["SIMULATED", "NATIVE_APP"],
            "caller.git_management": "standalone",
            "caller.kind": "direct",
            "review.independent_required": False,
            "request.review.independent_required": False,
        }
    resolved = policy.resolve_mode_gates(mode, facts)
    levels = {
        gate: policy.gate_min_level(mode, gate, facts)
        for gate in policy.GATE_IDS
        if resolved[gate] != "NOT_APPLICABLE"
    }
    _emit(
        {
            "ok": True,
            "mode": mode,
            "facts": facts,
            "gates": resolved,
            "derived_gates": policy.load_mode_gate_policy()["derived_gates"],
            "required_gates": policy.required_gates(mode, facts),
            "runtime_min_levels": levels,
            "l4_required": policy.l4_required(mode),
        }
    )
    return EXIT_OK


def cmd_finalize(args: argparse.Namespace) -> int:
    now = _parse_now(args.now)
    if now is None:
        _emit({"ok": False, "errors": [f"invalid --now timestamp: {args.now!r}"]})
        return EXIT_USAGE
    if args.repair_cycles is not None and not (0 <= args.repair_cycles <= 2):
        _emit({"ok": False, "errors": ["--repair-cycles must be within 0..2"]})
        return EXIT_USAGE
    loaded: dict[str, Any] = {}
    schema_errors: list[str] = []
    required_inputs = {
        "request": ("task-request", args.request),
        "gate_results": ("gate-results", args.gate_results),
        "coverage": ("coverage-matrix", args.coverage),
        "evidence_manifest": ("evidence-manifest", args.evidence_manifest),
    }
    for key, (schema_name, path) in required_inputs.items():
        try:
            loaded[key] = _load(path)
        except Exception as exc:  # noqa: BLE001
            schema_errors.append(f"{key}: cannot read {path}: {exc}")
            continue
        for error in contracts.validation_errors(schema_name, loaded[key]):
            schema_errors.append(f"{key}: {error}")

    try:
        tool_logs = _load_list(args.tool_logs)
    except Exception as exc:  # noqa: BLE001
        schema_errors.append(f"tool_logs: {exc}")
        tool_logs = []
    for index, log in enumerate(tool_logs):
        for error in contracts.validation_errors("tool-log", log):
            schema_errors.append(f"tool_logs[{index}]: {error}")

    design_review = None
    if args.design_review:
        try:
            design_review = _load(args.design_review)
            for error in contracts.validation_errors("design-review", design_review):
                schema_errors.append(f"design_review: {error}")
        except Exception as exc:  # noqa: BLE001
            schema_errors.append(f"design_review: {exc}")

    attestation = None
    if args.review_attestation:
        try:
            attestation = _load(args.review_attestation)
            for error in contracts.validation_errors("review-attestation", attestation):
                schema_errors.append(f"review_attestation: {error}")
        except Exception as exc:  # noqa: BLE001
            schema_errors.append(f"review_attestation: {exc}")

    warn_reviews: list[dict[str, Any]] = []
    try:
        warn_reviews = _load_list(args.warn_reviews)
    except Exception as exc:  # noqa: BLE001
        schema_errors.append(f"warn_reviews: {exc}")
    for index, review in enumerate(warn_reviews):
        for error in contracts.fragment_errors("common", "warn_review", review):
            schema_errors.append(f"warn_reviews[{index}]: {error}")

    if schema_errors:
        return _invalid(schema_errors, context="finalize inputs")

    request = loaded["request"]
    gate_results = loaded["gate_results"]
    coverage = loaded["coverage"]
    manifest = loaded["evidence_manifest"]

    for problem in validation.request_semantic_errors(request):
        schema_errors.append(f"request: {problem['code']}: {problem['detail']}")
    for problem in validation.gate_results_semantic_errors(gate_results):
        schema_errors.append(f"gate_results: {problem['code']}: {problem['detail']}")

    run_ids = {
        "request": request["run_id"],
        "gate_results": gate_results["run_id"],
        "coverage": coverage["run_id"],
        "evidence_manifest": manifest["run_id"],
    }
    if len(set(run_ids.values())) != 1:
        schema_errors.append(f"run_id mismatch across inputs: {run_ids}")
    if gate_results["mode"] != request["mode"]:
        schema_errors.append("gate_results.mode differs from request.mode")
    if gate_results.get("request_digest") and gate_results["request_digest"] != contracts.sha256_json(request):
        schema_errors.append("REQUEST_DIGEST_MISMATCH: gate_results.request_digest differs from current request")

    if schema_errors:
        return _invalid(schema_errors, context="finalize cross-checks")

    outcome = gates.evaluate_run(
        request=request,
        gate_results=gate_results,
        coverage=coverage,
        manifest=manifest,
        tool_logs=tool_logs,
        design_review=design_review,
        review_attestation=attestation,
        warn_reviews=warn_reviews,
        repair_cycles=args.repair_cycles or 0,
        now=now,
    )

    result = {
        "schema_version": "1.3.3",
        "run_id": request["run_id"],
        "mode": request["mode"],
        "status": outcome["status"],
        "delivery_status": outcome["delivery_status"],
        "independent_review_status": outcome["independent_review_status"],
        "design_review_status": outcome["design_review_status"],
        "source_fingerprint": gate_results["source_fingerprint"],
        "runtime_evidence_level": outcome["runtime_evidence_level"],
        "review_isolation_level": outcome["review_isolation_level"],
        "gates": gate_results["gates"],
        "derived_g6": outcome["derived_g6"],
        "coverage_matrix": outcome["coverage_matrix"],
        "unverified_paths": outcome["unverified_paths"],
        "blocking_reasons": outcome["blocking_reasons"],
        "warn_reviews": outcome["warn_reviews"],
        "evidence_manifest": args.evidence_manifest,
        "design_review_ref": args.design_review,
        "review_attestation_ref": args.review_attestation,
        "repair_cycles": outcome["repair_cycles"],
        "created_at": now.isoformat(),
    }

    result_errors = contracts.validation_errors("task-result", result)
    result_errors.extend(
        f"{item['code']}: {item['detail']}" for item in validation.result_semantic_errors(result, request, gate_results)
    )
    if result_errors:
        return _invalid(result_errors, context="generated task-result")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _emit(
        {
            "ok": outcome["status"] == "COMPLETE",
            "status": outcome["status"],
            "delivery_status": outcome["delivery_status"],
            "independent_review_status": outcome["independent_review_status"],
            "design_review_status": outcome["design_review_status"],
            "runtime_evidence_level": outcome["runtime_evidence_level"],
            "review_isolation_level": outcome["review_isolation_level"],
            "g6": outcome["derived_g6"]["state"],
            "resolved_gates": outcome["resolved_gates"],
            "blocking_reasons": outcome["blocking_reasons"],
            "unverified_paths": outcome["unverified_paths"],
            "out": args.out,
        }
    )
    return STATUS_EXIT.get(outcome["status"], EXIT_INVALID)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uiux-engine", description="Universal UI/UX Engineering engine (V1.3.3)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_enums = sub.add_parser("enums", help="print the canonical enum dictionary")
    p_enums.set_defaults(func=cmd_enums)

    p_validate = sub.add_parser("validate", help="validate one JSON instance against a contract schema")
    p_validate.add_argument("--schema", required=True, choices=sorted(contracts.SCHEMA_FILES))
    p_validate.add_argument("--instance", required=True)
    p_validate.set_defaults(func=cmd_validate)

    p_policy = sub.add_parser("policy", help="resolve the Mode×Gate policy for a mode or request")
    p_policy.add_argument("--mode", choices=sorted(enums.values("Mode")))
    p_policy.add_argument("--request")
    p_policy.set_defaults(func=cmd_policy)

    p_rules = sub.add_parser("rules", help="validate the frozen rule catalog (T1.0)")
    p_rules.add_argument("--catalog")
    p_rules.set_defaults(func=cmd_rules)

    p_snapshot = sub.add_parser("snapshot", help="non-Git directory digest / snapshot diff (M17)")
    p_snapshot.add_argument("--root")
    p_snapshot.add_argument("--out")
    p_snapshot.add_argument("--backup", help="copy tree to this new directory (rollback copy)")
    p_snapshot.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    p_snapshot.set_defaults(func=cmd_snapshot)

    p_input = sub.add_parser("input-policy", help="authorize an input channel (M6)")
    p_input.add_argument("--channel", required=True, choices=list(input_policy.CHANNELS))
    p_input.add_argument("--isolated", action="store_true")
    p_input.add_argument("--read-only", action="store_true")
    p_input.add_argument("--explicit", action="store_true")
    p_input.set_defaults(func=cmd_input_policy)

    p_guard = sub.add_parser("build-guard", help="guard an untrusted-project build command (M8)")
    p_guard.add_argument("--root", required=True)
    p_guard.add_argument("--command", required=True)
    p_guard.add_argument("--allow-network", action="store_true")
    p_guard.set_defaults(func=cmd_build_guard)

    p_knowledge = sub.add_parser("knowledge", help="verify the knowledge index/checksums (T2.4)")
    p_knowledge.add_argument("--index")
    p_knowledge.add_argument("--root")
    p_knowledge.set_defaults(func=cmd_knowledge)

    p_tokens = sub.add_parser("tokens", help="compile design tokens to css/tailwind/pyside6 (T2.3)")
    p_tokens.add_argument("--format", required=True, choices=["css", "tailwind", "pyside6"])
    p_tokens.add_argument("--out", required=True)
    p_tokens.set_defaults(func=cmd_tokens)

    p_modify = sub.add_parser("modify", help="validate/apply/revert a controlled change plan (T3.1)")
    p_modify.add_argument("--root", required=True)
    p_modify.add_argument("--plan", required=True)
    p_modify.add_argument("--apply", action="store_true")
    p_modify.add_argument("--backup")
    p_modify.add_argument("--revert")
    p_modify.set_defaults(func=cmd_modify)

    p_vault = sub.add_parser("vault", help="verify evidence bytes against a manifest (T3.5)")
    p_vault.add_argument("--root", required=True)
    p_vault.add_argument("--manifest", required=True)
    p_vault.add_argument("--quarantine")
    p_vault.set_defaults(func=cmd_vault)

    p_integrity = sub.add_parser("integrity", help="verify a persisted hash chain and attestation (T3.6)")
    p_integrity.add_argument("--chain", required=True)
    p_integrity.add_argument("--attestation")
    p_integrity.add_argument("--commit")
    p_integrity.set_defaults(func=cmd_integrity)

    p_safety = sub.add_parser("safety", help="classify a change plan P0-P3 (T3.7)")
    p_safety.add_argument("--plan", required=True)
    p_safety.set_defaults(func=cmd_safety)

    p_compat = sub.add_parser("compat", help="host degradation report (T4.4)")
    p_compat.add_argument("--agents-home")
    p_compat.set_defaults(func=cmd_compat)

    p_finalize = sub.add_parser("finalize", help="derive G6 and issue a TaskResult from evidence")
    p_finalize.add_argument("--request", required=True)
    p_finalize.add_argument("--gate-results", required=True)
    p_finalize.add_argument("--coverage", required=True)
    p_finalize.add_argument("--evidence-manifest", required=True)
    p_finalize.add_argument("--tool-logs")
    p_finalize.add_argument("--design-review")
    p_finalize.add_argument("--review-attestation")
    p_finalize.add_argument("--warn-reviews")
    p_finalize.add_argument("--repair-cycles", type=int, help="actual repair cycles performed (0..2)")
    p_finalize.add_argument("--now", help="frozen ISO8601 timestamp for reproducible tests")
    p_finalize.add_argument("--out")
    p_finalize.set_defaults(func=cmd_finalize)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
