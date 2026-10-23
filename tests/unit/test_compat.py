from __future__ import annotations

import json
from pathlib import Path

from uiux_engine import compat, external


def test_only_observed_host_is_marked_observed():
    matrix = compat.host_matrix("dsh", "evidence/T0.3/host-install-evidence.json")
    rows = {row["host"]: row for row in matrix["hosts"]}
    assert rows["dsh"]["status"] == "OBSERVED"
    assert rows["codex"]["status"] == "UNVERIFIED"
    assert matrix["verified_count"] == 1
    assert matrix["unverified_count"] == len(rows) - 1


def test_unverified_hosts_have_reason_code():
    matrix = compat.host_matrix("dsh", "x")
    for row in matrix["hosts"]:
        if row["status"] == "UNVERIFIED":
            assert row["reason_code"] == "HOST_UNVERIFIED"


def test_degradation_report_shape(tmp_path: Path):
    report = compat.degradation_report(tmp_path)
    ids = {check["id"] for check in report["checks"]}
    assert {"python", "node", "gui", "link-uiux", "link-uiux-verify"} <= ids
    assert isinstance(report["ok"], bool)


def test_missing_links_are_reported(tmp_path: Path):
    report = compat.degradation_report(tmp_path)
    link_checks = [check for check in report["checks"] if check["id"].startswith("link-")]
    assert all(check["reason_code"] == "LINK_MISSING" for check in link_checks)


def test_external_call_accepts_valid_request(tmp_path: Path):
    request = tmp_path / "request.json"
    request.write_text("{}", encoding="utf-8")
    result = external.accept_call({"caller": "ci", "task_id": "T-1", "request_path": "request.json", "role": "owner"}, tmp_path)
    assert result["accepted"] is True
    assert result["orchestrates"] is False


def test_external_call_rejects_missing_fields(tmp_path: Path):
    result = external.accept_call({"caller": "ci"}, tmp_path)
    assert result["accepted"] is False
    assert any("task_id" in problem for problem in result["problems"])


def test_external_call_rejects_unknown_role(tmp_path: Path):
    request = tmp_path / "request.json"
    request.write_text("{}", encoding="utf-8")
    result = external.accept_call({"caller": "ci", "task_id": "T-1", "request_path": "request.json", "role": "orchestrator"}, tmp_path)
    assert result["accepted"] is False


def test_external_call_rejects_missing_request_file(tmp_path: Path):
    result = external.accept_call({"caller": "ci", "task_id": "T-1", "request_path": "missing.json"}, tmp_path)
    assert result["accepted"] is False
