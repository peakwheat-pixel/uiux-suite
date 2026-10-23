"""ux_flow_validator (T1.3): deterministic flow-contract checks.

Only the frozen rule ids from `knowledge/rules/catalog.v1.0.json` are emitted.
Reachability is bounded by the flow contract: a task's entry point and runtime
assertions must reference declared states; destructive/empty/error/loading
states are checked against declared capabilities.
"""
from __future__ import annotations

import re
from typing import Any

from . import contracts, rules

FLOW_RULES = {
    "UX-FLOW-001": "FAIL",
    "UX-FLOW-002": "FAIL",
    "UX-FLOW-003": "WARNING",
    "UX-FLOW-004": "FAIL",
    "UX-STATE-001": "WARNING",
    "UX-STATE-002": "WARNING",
}
EMPTY_PATTERNS = re.compile(r"(empty|no[-_ ]?data|zero|空白|无数据|空状态)", re.IGNORECASE)
ERROR_PATTERNS = re.compile(r"(error|fail|retry|recover|异常|错误|失败|重试|恢复)", re.IGNORECASE)
LOADING_PATTERNS = re.compile(r"(loading|pending|progress|加载|处理中|进度)", re.IGNORECASE)
DIRTY_PATTERNS = re.compile(r"(dirty|unsaved|save|draft|未保存|草稿|保存)", re.IGNORECASE)


def _finding(rule_id: str, message: str, *, task_id: str | None = None, state: str | None = None) -> dict[str, Any]:
    finding = {
        "rule_id": rule_id,
        "severity": FLOW_RULES[rule_id],
        "message": message,
    }
    if task_id:
        finding["task_id"] = task_id
    if state:
        finding["state"] = state
    return finding


def validate(flows: dict[str, Any]) -> dict[str, Any]:
    schema_errors = contracts.validation_errors("flows", flows)
    findings: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []

    if schema_errors:
        for error in schema_errors:
            findings.append(
                {
                    "rule_id": "UX-FLOW-001",
                    "severity": "FAIL",
                    "message": f"flows schema invalid: {error}",
                }
            )
        return _report(findings, unverified, schema_valid=False)

    catalog_ids = {rule["rule_id"] for rule in rules.load_catalog()["rules"]}
    for rule_id in FLOW_RULES:
        if rule_id not in catalog_ids:  # pragma: no cover - frozen catalog guard
            raise ValueError(f"rule id {rule_id} is not in the frozen catalog")

    capabilities = flows["capabilities"]
    tasks = flows["tasks"]
    seen_task_ids: set[str] = set()
    declared_states: set[str] = set()

    for task in tasks:
        task_id = task["task_id"]
        if task_id in seen_task_ids:
            findings.append(_finding("UX-FLOW-001", f"duplicate task_id: {task_id}", task_id=task_id))
        seen_task_ids.add(task_id)
        states = list(task["states"])
        declared_states.update(states)
        if task["entry_point"] not in states:
            findings.append(
                _finding(
                    "UX-FLOW-001",
                    f"entry_point {task['entry_point']!r} is not a declared state",
                    task_id=task_id,
                    state=task["entry_point"],
                )
            )
        for assertion in task["runtime_assertions"]:
            if not assertion["expected_states"]:
                continue
            missing = [state for state in assertion["expected_states"] if state not in states]
            for state in missing:
                findings.append(
                    _finding(
                        "UX-FLOW-001",
                        f"assertion {assertion['assertion_id']} expects undeclared state {state!r}",
                        task_id=task_id,
                        state=state,
                    )
                )
        _check_task_guards(task, capabilities, findings)

    if capabilities.get("collection_display") and not _has_pattern(declared_states, EMPTY_PATTERNS):
        findings.append(_finding("UX-FLOW-003", "collection capability has no empty state"))
    if (capabilities.get("async_load") or capabilities.get("long_running_task")) and not _has_pattern(
        declared_states, ERROR_PATTERNS
    ):
        findings.append(_finding("UX-FLOW-004", "async/long-running flow has no error or retry state"))
    if capabilities.get("async_load") and not _has_pattern(declared_states, LOADING_PATTERNS):
        findings.append(_finding("UX-STATE-001", "async_load flow has no loading state"))
    if (
        capabilities.get("user_mutation")
        and flows["view_archetype"] == "desktop_workbench"
        and not _has_pattern(declared_states, DIRTY_PATTERNS)
    ):
        findings.append(_finding("UX-STATE-002", "desktop workbench has no unsaved/draft state"))
    if capabilities.get("destructive_operations") and not any(
        task["destructive_operations"] for task in tasks
    ):
        findings.append(_finding("UX-FLOW-002", "destructive_operations capability declared but no operation is modeled"))

    evidenced = {(item["capability"], item["discovery"]) for item in flows["capability_evidence"]}
    for capability, enabled in capabilities.items():
        if enabled and not any(item[0] == capability for item in evidenced):
            unverified.append(
                {
                    "capability": capability,
                    "reason_code": "UNVERIFIED_PATH",
                    "detail": "capability declared true without capability_evidence",
                }
            )

    return _report(findings, unverified, schema_valid=True)


def _check_task_guards(task: dict[str, Any], capabilities: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for operation in task["destructive_operations"]:
        guard = operation["guard"]
        if operation["irreversible"] and guard == "none":
            findings.append(
                _finding(
                    "UX-FLOW-002",
                    f"irreversible operation {operation['operation_id']} has guard=none",
                    task_id=task["task_id"],
                )
            )
        elif guard == "none":
            findings.append(
                _finding(
                    "UX-FLOW-002",
                    f"destructive operation {operation['operation_id']} has guard=none",
                    task_id=task["task_id"],
                )
            )
        if guard in ("confirmation", "undo", "both") and not operation.get("evidence_refs"):
            findings.append(
                _finding(
                    "UX-FLOW-002",
                    f"operation {operation['operation_id']} declares guard={guard} without evidence",
                    task_id=task["task_id"],
                )
            )
    if capabilities.get("destructive_operations") and not task["destructive_operations"]:
        # The global check reports once; tasks with explicit destructive state
        # but no operation are already covered by schema-level capability checks.
        return


def _has_pattern(states: set[str], pattern: re.Pattern[str]) -> bool:
    return any(pattern.search(state) for state in states)


def _report(findings: list[dict[str, Any]], unverified: list[dict[str, Any]], *, schema_valid: bool) -> dict[str, Any]:
    summary = {"fail": 0, "warning": 0, "info": 0}
    for finding in findings:
        summary[finding["severity"].lower()] += 1
    return {
        "ok": schema_valid and summary["fail"] == 0,
        "schema_valid": schema_valid,
        "findings": findings,
        "summary": summary,
        "unverified_paths": unverified,
    }
