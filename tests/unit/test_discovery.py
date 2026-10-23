from __future__ import annotations

import json
from pathlib import Path

import pytest

from uiux_engine import contracts, discovery

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "discovery"
SAMPLE = FIXTURES / "sample-app"
UNGUARDED = FIXTURES / "unguarded-app"
EDGE = FIXTURES / "edge-app"


def test_discovery_schema_valid():
    report = discovery.discover(SAMPLE)
    assert contracts.validation_errors("discovery", report) == []


def test_routes_are_discovered_with_line_numbers():
    report = discovery.discover(SAMPLE)
    routes = {page["route"]: page for page in report["pages"] if page["kind"] == "route"}
    assert set(routes) == {"/orders", "/orders/:id", "/settings"}
    for page in routes.values():
        assert page["source"]["file"] == "src/router.tsx"
        assert page["source"]["line"] >= 1


def test_component_pages_and_dialog_kind():
    report = discovery.discover(SAMPLE)
    pages = {page["page_id"]: page for page in report["pages"]}
    assert pages["OrdersPage"]["kind"] == "page"
    assert pages["SettingsDialog"]["kind"] == "dialog"
    assert pages["OrdersPage"]["archetype"] == "data_table"


def test_qt_windows_are_discovered():
    report = discovery.discover(SAMPLE)
    windows = [page for page in report["pages"] if page["kind"] == "window"]
    assert {page["page_id"] for page in windows} >= {"MainWindow", "CanvasView"}
    assert any(page["archetype"] == "canvas_editor" for page in windows)


def test_capabilities_are_observed_with_evidence():
    report = discovery.discover(SAMPLE)
    caps = report["capabilities"]
    assert caps["async_load"] is True
    assert caps["collection_display"] is True
    assert caps["long_running_task"] is True
    assert caps["canvas_rendering"] is True
    evidenced = {item["capability"] for item in report["capability_evidence"]}
    assert {"async_load", "collection_display", "long_running_task"} <= evidenced
    for item in report["capability_evidence"]:
        assert item["source"]["ref"]
        assert item["source"]["locator"].startswith("line ")


def test_runtime_and_contract_sources_are_honest():
    report = discovery.discover(SAMPLE)
    sources = {item["source"]: item for item in report["sources"]}
    assert sources["source"]["status"] == "OBSERVED"
    assert sources["runtime"]["status"] == "UNVERIFIED"
    assert sources["contract"]["status"] == "MISSING"
    assert report["unverified_paths"]


def test_flows_generated_from_discovery_are_schema_valid():
    report = discovery.discover(SAMPLE)
    flows = discovery.flows_from_discovery(report)
    assert contracts.validation_errors("flows", flows) == []
    assert flows["view_id"] == report["view_id"]
    states = {state for task in flows["tasks"] for state in task["states"]}
    assert {"list", "loading", "error", "empty"} <= states


def test_no_capability_is_claimed_without_evidence():
    report = discovery.discover(EDGE)
    for capability, enabled in report["capabilities"].items():
        if enabled:
            assert any(item["capability"] == capability for item in report["capability_evidence"])


def test_static_page_has_no_destructive_capability():
    report = discovery.discover(EDGE)
    assert report["capabilities"]["destructive_operations"] is False
    assert report["pages"]


def test_unguarded_delete_is_detected():
    report = discovery.discover(UNGUARDED)
    assert report["capabilities"]["destructive_operations"] is True
    assert any(item["capability"] == "destructive_operations" for item in report["capability_evidence"])


def test_missing_directory_is_rejected():
    with pytest.raises(ValueError):
        discovery.discover(FIXTURES / "does-not-exist")


def test_deterministic_output():
    assert discovery.discover(SAMPLE) == discovery.discover(SAMPLE)


def test_report_can_be_written_and_reloaded(tmp_path: Path):
    report = discovery.discover(SAMPLE)
    path = tmp_path / "discovery.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == report
