"""UIA tree model and accessibility/geometry checks (T3.4/M18)."""
from __future__ import annotations

from typing import Any

from . import rules

INTERACTIVE_TYPES = {
    "ControlType.Button",
    "ControlType.Edit",
    "ControlType.Hyperlink",
    "ControlType.CheckBox",
    "ControlType.RadioButton",
    "ControlType.ComboBox",
    "ControlType.ListItem",
    "ControlType.MenuItem",
    "ControlType.TabItem",
    "ControlType.Slider",
}
SEVERITY = {"UX-A11Y-001": "FAIL", "UX-SPACE-002": "FAIL", "UX-GEOM-001": "FAIL"}
MIN_TARGET = 24.0


def _catalog_guard() -> None:
    known = {rule["rule_id"] for rule in rules.load_catalog()["rules"]}
    missing = set(SEVERITY) - known
    if missing:
        raise ValueError(f"rule ids not in frozen catalog: {sorted(missing)}")


def _walk(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat = []
    for element in elements:
        flat.append(element)
        flat.extend(_walk(element.get("children", [])))
    return flat


def findings(dump: dict[str, Any]) -> dict[str, Any]:
    _catalog_guard()
    flat = _walk(dump.get("elements", []))
    found: list[dict[str, Any]] = []
    for element in flat:
        control_type = element.get("control_type")
        name = (element.get("name") or "").strip()
        if control_type in INTERACTIVE_TYPES and not name:
            found.append(
                {
                    "rule_id": "UX-A11Y-001",
                    "severity": SEVERITY["UX-A11Y-001"],
                    "message": f"{control_type} has no accessible name (automation_id={element.get('automation_id')!r})",
                    "control_type": control_type,
                }
            )
        bounds = element.get("bounds") or {}
        width = float(bounds.get("width", 0) or 0)
        height = float(bounds.get("height", 0) or 0)
        if control_type in INTERACTIVE_TYPES and (0 < width < MIN_TARGET or 0 < height < MIN_TARGET):
            found.append(
                {
                    "rule_id": "UX-SPACE-002",
                    "severity": SEVERITY["UX-SPACE-002"],
                    "message": f"target {width}x{height} below {MIN_TARGET}px",
                    "control_type": control_type,
                }
            )
        if control_type in INTERACTIVE_TYPES and element.get("is_offscreen") is True:
            found.append(
                {
                    "rule_id": "UX-GEOM-001",
                    "severity": SEVERITY["UX-GEOM-001"],
                    "message": "interactive element is offscreen/clipped",
                    "control_type": control_type,
                }
            )
    summary = {"fail": 0, "warning": 0, "info": 0}
    for item in found:
        summary[item["severity"].lower()] += 1
    return {
        "ok": summary["fail"] == 0,
        "runtime_level": dump.get("runtime_level", "UNKNOWN"),
        "element_count": len(flat),
        "findings": found,
        "summary": summary,
        "limitations": dump.get("limitations", []),
    }
