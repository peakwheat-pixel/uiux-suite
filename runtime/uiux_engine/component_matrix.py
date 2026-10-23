"""Component/state coverage matrix (T2.5)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import contracts

COMPONENT_PATTERNS = (
    re.compile(r"\bfunction\s+([A-Z][A-Za-z0-9_]*)\s*\("),
    re.compile(r"\bclass\s+([A-Z][A-Za-z0-9_]*)\s*[({:]"),
    re.compile(r"\bconst\s+([A-Z][A-Za-z0-9_]*)\s*=\s*(?:\(|function|React\.)"),
    re.compile(r"\bclass\s+([A-Z][A-Za-z0-9_]*)\s*\(.*QWidget"),
)
SOURCE_SUFFIXES = {".tsx", ".ts", ".jsx", ".js", ".py", ".ui"}
DEFAULT_STATES = ("loading", "empty", "error", "ready", "saved", "draft")


def scan_components(root: str | Path, states: list[str] | None = None) -> list[dict[str, Any]]:
    root_path = Path(root)
    states = states or list(DEFAULT_STATES)
    components: list[dict[str, Any]] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        names = []
        for pattern in COMPONENT_PATTERNS:
            names.extend(pattern.findall(text))
        for name in dict.fromkeys(names):
            lowered = text.lower()
            covered = [state for state in states if f'data-state="{state}"' in lowered or f"'{state}'" in lowered or f'"{state}"' in lowered]
            components.append(
                {
                    "component_id": name,
                    "source": path.relative_to(root_path).as_posix(),
                    "states": states,
                    "covered_states": covered,
                    "gaps": [state for state in states if state not in covered],
                }
            )
    return components


def build_matrix(flows: dict[str, Any], root: str | Path) -> dict[str, Any]:
    flow_states: list[str] = []
    for task in flows["tasks"]:
        for state in task["states"]:
            if state not in flow_states:
                flow_states.append(state)
    components = scan_components(root, flow_states or None)
    coverage = []
    for state in flow_states:
        covering = [component["component_id"] for component in components if state in component["covered_states"]]
        coverage.append({"state": state, "covered": bool(covering), "components": covering})
    gaps = sum(1 for item in coverage if not item["covered"])
    matrix = {
        "schema_version": "1.3.3",
        "view_id": flows.get("view_id", "unknown"),
        "components": components,
        "state_coverage": coverage,
        "summary": {
            "components": len(components),
            "states": len(flow_states),
            "covered": len(flow_states) - gaps,
            "gaps": gaps,
        },
    }
    return matrix


def validate_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    errors = contracts.validation_errors("component-matrix", matrix)
    warnings: list[str] = []
    if not errors:
        declared = {item["state"] for item in matrix["state_coverage"]}
        for component in matrix["components"]:
            for missing in component["gaps"]:
                if missing not in declared:
                    warnings.append(f"{component['component_id']}: gap {missing} is not declared in state_coverage")
        if matrix["summary"]["gaps"]:
            warnings.append(f"{matrix['summary']['gaps']} state(s) have no component coverage")
    return {"ok": not errors and not matrix["summary"]["gaps"], "errors": errors, "warnings": warnings}
