from __future__ import annotations

import json
from pathlib import Path

from uiux_engine import component_matrix

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "component_matrix"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_matrix_schema_valid():
    matrix = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    assert matrix["summary"]["components"] == 2
    assert matrix["summary"]["states"] == 6
    assert component_matrix.validate_matrix(matrix)["errors"] == []


def test_scan_detects_components_and_states():
    matrix = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    components = {item["component_id"]: item for item in matrix["components"]}
    assert set(components) == {"OrdersTable", "OrderToolbar"}
    assert "loading" in components["OrdersTable"]["covered_states"]
    assert "error" in components["OrdersTable"]["covered_states"]
    assert components["OrdersTable"]["gaps"]


def test_uncovered_states_are_reported():
    matrix = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    report = component_matrix.validate_matrix(matrix)
    assert report["ok"] is False
    assert report["warnings"]


def test_state_coverage_points_to_components():
    matrix = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    coverage = {item["state"]: item for item in matrix["state_coverage"]}
    assert coverage["loading"]["covered"] is True
    assert "OrdersTable" in coverage["loading"]["components"]
    assert coverage["saved"]["covered"] is False


def test_invalid_flows_states_do_not_crash():
    flows = load("flows.json")
    flows["tasks"][0]["states"] = []
    try:
        component_matrix.build_matrix(flows, FIXTURES / "project")
    except Exception as exc:  # noqa: BLE001 - explicit contract: must not crash on empty states
        raise AssertionError(f"unexpected exception: {exc}") from exc


def test_empty_project_has_no_components():
    matrix = component_matrix.build_matrix(load("flows.json"), FIXTURES / "does-not-exist")
    assert matrix["components"] == []
    assert matrix["summary"]["gaps"] == matrix["summary"]["states"]


def test_invalid_matrix_is_rejected():
    matrix = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    matrix["summary"]["components"] = -1
    assert component_matrix.validate_matrix(matrix)["errors"]


def test_deterministic_output():
    first = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    second = component_matrix.build_matrix(load("flows.json"), FIXTURES / "project")
    assert first == second
