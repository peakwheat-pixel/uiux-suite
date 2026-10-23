"""Prototype contract checks (T2.6)."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from . import contracts

TESTID_RE = re.compile(r'data-testid\s*=\s*["\']([^"\']+)["\']')
STATE_RE = re.compile(r'data-state\s*=\s*["\']([^"\']+)["\']')


class _Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.testids: set[str] = set()
        self.states: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapping = dict(attrs)
        if mapping.get("data-testid"):
            self.testids.add(mapping["data-testid"])
        if mapping.get("data-state"):
            self.states.add(mapping["data-state"])


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(prototype: dict[str, Any], root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    errors = contracts.validation_errors("prototype", prototype)
    checks: list[dict[str, str]] = []
    if errors:
        return {
            "ok": False,
            "overall_status": "FAIL",
            "checks": [{"check_id": "schema", "status": "FAIL", "detail": error} for error in errors],
            "errors": errors,
        }

    flows_path = root_path / prototype["flows_ref"]
    flows: dict[str, Any] | None = None
    if not flows_path.is_file():
        checks.append({"check_id": "flows-ref", "status": "FAIL", "detail": f"missing flows: {prototype['flows_ref']}"})
    else:
        flows = _load_json(flows_path)
        flow_states = {state for task in flows["tasks"] for state in task["states"]}
        unknown = [state for state in prototype["states"] if state not in flow_states]
        checks.append(
            {
                "check_id": "states-subset",
                "status": "FAIL" if unknown else "PASS",
                "detail": f"unknown states: {sorted(unknown)}" if unknown else "all prototype states exist in flows",
            }
        )
        flow_anchors = {anchor["semantic_id"] for anchor in flows["ui_anchors"]}
        unknown_anchors = [anchor["semantic_id"] for anchor in prototype["anchors"] if anchor["semantic_id"] not in flow_anchors]
        checks.append(
            {
                "check_id": "anchors-known",
                "status": "FAIL" if unknown_anchors else "PASS",
                "detail": f"unknown anchors: {unknown_anchors}" if unknown_anchors else "all anchors known to flows",
            }
        )

    if prototype.get("source_file"):
        source = root_path / prototype["source_file"]
        if not source.is_file():
            checks.append({"check_id": "source-file", "status": "FAIL", "detail": f"missing prototype source: {prototype['source_file']}"})
        elif prototype["kind"] == "html":
            scan = _Scan()
            scan.feed(source.read_text(encoding="utf-8", errors="ignore"))
            missing_testids = [anchor["semantic_id"] for anchor in prototype["anchors"] if anchor.get("testid") and anchor["testid"] not in scan.testids]
            checks.append(
                {
                    "check_id": "html-testids",
                    "status": "FAIL" if missing_testids else "PASS",
                    "detail": f"missing data-testid: {missing_testids}" if missing_testids else "all testids present",
                }
            )
            missing_states = [state for state in prototype["states"] if state not in scan.states]
            checks.append(
                {
                    "check_id": "html-states",
                    "status": "FAIL" if missing_states else "PASS",
                    "detail": f"missing data-state: {missing_states}" if missing_states else "all states present",
                }
            )

    for name, status in prototype["accessibility"].items():
        if status == "FAIL":
            checks.append({"check_id": f"a11y-{name}", "status": "FAIL", "detail": f"{name} verification failed"})
        elif status == "UNVERIFIED":
            checks.append({"check_id": f"a11y-{name}", "status": "UNVERIFIED", "detail": f"{name} not verified"})
        else:
            checks.append({"check_id": f"a11y-{name}", "status": "PASS", "detail": f"{name} verified"})
    for item in prototype["checks"]:
        checks.append(item)

    statuses = {item["status"] for item in checks}
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "UNVERIFIED" in statuses:
        overall = "UNVERIFIED"
    else:
        overall = "PASS"
    return {"ok": overall == "PASS", "overall_status": overall, "checks": checks, "errors": []}
