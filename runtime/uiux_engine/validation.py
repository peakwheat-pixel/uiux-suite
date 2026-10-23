"""Cross-field semantic checks that JSON Schema cannot express (V1.3.3)."""
from __future__ import annotations

import os
from typing import Any

from .enums import reason_codes

MUTATING_MODES = {"new-build", "redesign", "targeted-fix"}
READ_ONLY_MODES = {"audit", "design-only", "prototype", "verify"}


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _overlaps(a: str, b: str) -> bool:
    na, nb = _norm(a).rstrip("\\/"), _norm(b).rstrip("\\/")
    return na == nb or na.startswith(nb + os.sep) or nb.startswith(na + os.sep)


def request_semantic_errors(request: dict[str, Any]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        problems.append({"code": code, "detail": detail})

    mode = request["mode"]
    policy = request["policy"]
    execution = request["execution_policy"]
    auth = policy.get("authorization")

    if mode not in policy["allowed_modes"]:
        add("POLICY_INVALID", f"mode {mode} not allowed by policy.allowed_modes")

    if request["caller"]["git_management"] != policy["git"]["management"]:
        add("POLICY_INVALID", "caller.git_management differs from policy.git.management")

    roots = policy["roots"]
    write_roots = {
        "report_write_root": roots["report_write_root"],
        "sandbox_write_root": roots["sandbox_write_root"],
        "install_write_root": roots["install_write_root"],
    }
    names = list(write_roots)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            if _overlaps(write_roots[left], write_roots[right]):
                add("POLICY_INVALID", f"{left} overlaps {right}")

    if mode in READ_ONLY_MODES and execution["allowed_write_globs"]:
        add("READ_ONLY_VIOLATION", "read-only modes must not declare source write globs")

    scope_globs = set(roots["source_write_scope"]["allowed_globs"])
    exec_globs = set(execution["allowed_write_globs"])
    if not scope_globs.issubset(exec_globs):
        add("WRITE_SCOPE_VIOLATION", "policy.source_write_scope is not a subset of execution.allowed_write_globs")

    if execution["allow_physical_os_input"]:
        if not policy["permissions"]["os_input"]["physical"]:
            add("OS_INPUT_NOT_ALLOWED", "physical OS input requested but policy forbids it")
        if not auth or "os_input_physical" not in auth.get("scopes", []):
            add("AUTHORIZATION_MISSING", "physical OS input requires authorization scope os_input_physical")

    if execution["allow_uia_input"] and not policy["permissions"]["os_input"]["uia_patterns"]:
        add("OS_INPUT_NOT_ALLOWED", "UIA input requested but policy forbids UIA patterns")

    if execution["allow_production_data_write"]:
        if not auth or "production_data_write" not in auth.get("scopes", []):
            add("AUTHORIZATION_MISSING", "production data write requires authorization scope production_data_write")

    if mode in MUTATING_MODES and execution["allowed_write_globs"]:
        if not auth or "production_write" not in auth.get("scopes", []):
            add("AUTHORIZATION_MISSING", "production source writes require authorization scope production_write")

    if execution["require_native_for_production_complete"] and mode in MUTATING_MODES:
        if "NATIVE_APP" not in request["runtime_targets"]:
            add("RUNTIME_TARGET_NOT_COVERED", "require_native_for_production_complete needs NATIVE_APP in runtime_targets")

    if request["evidence_policy"]["release_retention_days"] < request["evidence_policy"]["retention_days"]:
        add("POLICY_INVALID", "release_retention_days must be >= retention_days")

    if request["caller"]["kind"] == "direct" and request["caller"]["git_management"] == "caller_managed":
        add("POLICY_INVALID", "direct caller cannot use caller_managed git mode")

    if execution["allow_physical_os_input"] and not execution["os_input_target_allowlist"]:
        add("AUTHORIZATION_MISSING", "physical OS input requires a non-empty target allowlist")

    return problems


def result_semantic_errors(
    result: dict[str, Any],
    request: dict[str, Any],
    gate_results: dict[str, Any],
) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        problems.append({"code": code, "detail": detail})

    if result["run_id"] != request["run_id"]:
        add("RESULT_INVALID", "result.run_id differs from request.run_id")
    if result["mode"] != request["mode"]:
        add("RESULT_INVALID", "result.mode differs from request.mode")
    if result["source_fingerprint"] != gate_results["source_fingerprint"]:
        add("SOURCE_FINGERPRINT_MISMATCH", "result source fingerprint differs from gate-results")

    g6_state = result["derived_g6"]["state"]
    if result["status"] == "COMPLETE" and g6_state != "PASS":
        add("COMPLETE_CONSTRAINT_VIOLATION", "COMPLETE requires derived G6 PASS")
    if result["status"] != "COMPLETE" and g6_state == "PASS":
        add("RESULT_INVALID", "G6 must not be PASS when run status is not COMPLETE")

    for reason in result.get("blocking_reasons", []):
        code = reason.get("code")
        if not isinstance(code, str) or not code:
            add("RESULT_INVALID", "blocking reason code must be a non-empty string")
        elif code not in reason_codes():
            add("RESULT_INVALID", f"blocking reason code is not registered: {code}")

    return problems
