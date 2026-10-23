"""Mode×Gate policy resolution (V1.3.3).

The matrix is data, not prose: every gate resolves to one of
MANDATORY / REVIEW_ONLY / CONDITIONAL / NOT_APPLICABLE. Conditions are
evaluated against declared facts derived from a validated TaskRequest.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .enums import CONTRACTS_DIR, rank

POLICY_PATH = CONTRACTS_DIR / "mode-gate-policy.v1.3.3.json"
GATE_IDS = ("G0", "G1", "G2", "G3", "G4", "G5")
APPLICABILITY = ("MANDATORY", "REVIEW_ONLY", "CONDITIONAL", "NOT_APPLICABLE")


@lru_cache(maxsize=1)
def load_mode_gate_policy() -> dict[str, Any]:
    doc = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if doc.get("schema_version") != "1.3.3":
        raise ValueError("unexpected mode-gate policy version")
    return doc


def facts_from_request(request: dict[str, Any]) -> dict[str, Any]:
    mode = request["mode"]
    project = request.get("project") or {}
    has_ui = project.get("has_existing_ui")
    if has_ui is None:
        has_ui = mode in ("audit", "redesign", "targeted-fix", "verify")
    execution = request["execution_policy"]
    return {
        "mode": mode,
        "project.has_existing_ui": bool(has_ui),
        "request.read_only_source": bool(execution["read_only_source"]),
        "request.target_scope_nonempty": bool(request.get("target_scope")),
        "request.execution_policy.require_native_for_production_complete": bool(
            execution["require_native_for_production_complete"]
        ),
        "request.evidence_policy.profile": request["evidence_policy"]["profile"],
        "runtime_targets": list(request["runtime_targets"]),
        "caller.git_management": request["caller"]["git_management"],
        "caller.kind": request["caller"]["kind"],
        "review.independent_required": bool(request["review"]["independent_required"]),
    }


def _compare(fact_value: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return fact_value == expected
    if op == "neq":
        return fact_value != expected
    if op == "in":
        return fact_value in expected
    if op == "contains":
        return isinstance(fact_value, (list, tuple, set)) and expected in fact_value
    if op == "nonempty":
        return bool(fact_value)
    if op == "truthy":
        return bool(fact_value)
    if op == "falsy":
        return not fact_value
    raise ValueError(f"unsupported condition op: {op!r}")


def eval_condition(condition: dict[str, Any], facts: dict[str, Any]) -> bool:
    if "all" in condition:
        return all(eval_condition(item, facts) for item in condition["all"])
    if "any" in condition:
        return any(eval_condition(item, facts) for item in condition["any"])
    if "not" in condition:
        return not eval_condition(condition["not"], facts)
    fact = condition["fact"]
    if fact not in facts:
        raise KeyError(f"condition references undeclared fact: {fact!r}")
    return _compare(facts[fact], condition.get("op", "eq"), condition.get("value"))


def resolve_applicability(
    mode: str,
    gate: str,
    facts: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> str:
    policy = policy or load_mode_gate_policy()
    if mode not in policy["modes"]:
        raise KeyError(f"unknown mode {mode!r}")
    if gate not in policy["modes"][mode]["gates"]:
        raise KeyError(f"gate {gate!r} is not declared for mode {mode!r}")
    cell = policy["modes"][mode]["gates"][gate]
    applicability = cell["applicability"] if isinstance(cell, dict) else cell
    if applicability == "CONDITIONAL":
        if not isinstance(cell, dict) or "when" not in cell:
            raise ValueError(f"CONDITIONAL gate {mode}/{gate} lacks a when-condition")
        fallback = cell.get("else", "NOT_APPLICABLE")
        return "MANDATORY" if eval_condition(cell["when"], facts) else fallback
    if applicability not in APPLICABILITY or applicability == "CONDITIONAL":
        raise ValueError(f"invalid applicability {applicability!r} at {mode}/{gate}")
    return applicability


def resolve_mode_gates(
    mode: str,
    facts: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, str]:
    policy = policy or load_mode_gate_policy()
    return {gate: resolve_applicability(mode, gate, facts, policy) for gate in GATE_IDS}


def required_gates(
    mode: str,
    facts: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> list[str]:
    resolved = resolve_mode_gates(mode, facts, policy)
    return [gate for gate, app in resolved.items() if app == "MANDATORY"]


def l4_required(mode: str, policy: dict[str, Any] | None = None) -> bool:
    policy = policy or load_mode_gate_policy()
    return bool(policy["modes"][mode].get("l4_required"))


def independent_review_required(
    mode: str,
    request: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> bool:
    policy = policy or load_mode_gate_policy()
    if policy["modes"][mode].get("independent_review_required"):
        return True
    if request["review"]["independent_required"]:
        return True
    facts = facts_from_request(request)
    condition = policy["design_review_policy"].get("independent_review_when")
    return bool(condition and eval_condition(condition, facts))


def gate_min_level(
    mode: str,
    gate: str,
    facts: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> str:
    policy = policy or load_mode_gate_policy()
    default = policy["runtime_policy"]["default_gate_levels"].get(mode, {}).get(gate, "NONE")
    level = default
    for override in policy["runtime_policy"].get("level_overrides", []):
        if override.get("gate") != gate:
            continue
        if eval_condition(override["when"], facts):
            candidate = override["min_level"]
            if rank("RuntimeEvidenceLevel", candidate) > rank("RuntimeEvidenceLevel", level):
                level = candidate
    return level


def derive_runtime_targets(request: dict[str, Any]) -> list[str]:
    targets = list(request["runtime_targets"])
    if request["execution_policy"]["require_native_for_production_complete"] and "NATIVE_APP" not in targets:
        targets.append("NATIVE_APP")
    return targets
