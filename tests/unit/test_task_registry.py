from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_registry():
    return json.loads((REPO_ROOT / "plan" / "tasks.v1.3.3.json").read_text(encoding="utf-8"))


def test_registry_covers_all_remediation_findings():
    tasks = load_registry()["tasks"]
    ids = {item["id"] for item in tasks}
    assert {f"M{i}" for i in range(1, 19)} <= ids
    assert {f"m{i}" for i in range(1, 9)} <= ids


def test_registry_dependencies_resolve_and_are_acyclic():
    tasks = load_registry()["tasks"]
    graph = {item["id"]: item["depends_on"] for item in tasks}
    for task_id, deps in graph.items():
        for dependency in deps:
            assert dependency in graph, f"{task_id} depends on unknown {dependency}"
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        assert state.get(node) != 1, f"cycle at {node}"
        if state.get(node) == 2:
            return
        state[node] = 1
        for dependency in graph[node]:
            visit(dependency)
        state[node] = 2

    for node in graph:
        visit(node)


def test_registry_tasks_have_acceptance_and_valid_stage():
    stages = {"Stage 0", "Stage 1", "Stage 2", "Stage 3", "Stage 4", "Stage 5"}
    for item in load_registry()["tasks"]:
        assert item["acceptance"].strip()
        assert item["stage"] in stages
        assert item["status"] in {"DONE", "IN_PROGRESS", "TODO", "BLOCKED"}
        if item["status"] == "DONE":
            assert item["evidence"], f"{item['id']} is DONE without evidence"


def test_rendered_plan_is_in_sync():
    tasks = load_registry()["tasks"]
    plan = (REPO_ROOT / "docs" / "TASK_PLAN.md").read_text(encoding="utf-8")
    for item in tasks:
        assert f"| {item['id']} |" in plan, f"{item['id']} missing from rendered plan"
