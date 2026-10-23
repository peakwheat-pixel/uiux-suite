"""Static UI discovery and flows generation (T2.1/T2.2)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import contracts, rules

SOURCE_SUFFIXES = {".tsx", ".jsx", ".ts", ".js", ".html", ".ui", ".qml"}
IGNORED_PARTS = {".git", "__pycache__", "node_modules", ".venv", "dist", "build"}

ROUTE_RE = re.compile(r'path\s*:\s*["\']([^"\']+)["\'][^}]*?element\s*:\s*<([A-Za-z0-9_]+)', re.DOTALL)
EXPORT_FN_RE = re.compile(r"export\s+function\s+([A-Za-z0-9_]+)")
CLASS_RE = re.compile(r"<class>([A-Za-z0-9_]+)</class>|<widget\s+class=\"(Q[A-Za-z0-9_]+)\"\s+name=\"([A-Za-z0-9_]+)\"")
TESTID_RE = re.compile(r'data-testid\s*=\s*["\']([^"\']+)["\']')

CAPABILITY_PATTERNS = {
    "async_load": [r"\bfetch\s*\(", r"\baxios\b", r"useQuery\s*\(", r"QNetworkAccessManager", r"async\s+function"],
    "collection_display": [r"\.map\s*\(", r"<table", r"QTableView", r"QListView", r"QTreeView", r"<tbody"],
    "user_mutation": [r"<form", r"onSubmit", r"useState\s*\(", r"QLineEdit", r"QPushButton"],
    "long_running_task": [r"QProgressBar", r"progress", r"worker", r"QThread", r"AbortController"],
    "destructive_operations": [r"method\s*:\s*[\"']DELETE", r"\bdelete\b", r"\bremove\b", r"\bpurge\b", r"window\.confirm", r"trash"],
    "canvas_rendering": [r"<canvas", r"QGraphicsView", r"getContext\s*\(", r"WebGL", r"three"],
}
ARCHETYPE_RULES = [
    (r"QTableView|<table|data-table", "data_table"),
    (r"role=\"dialog\"|modal|QDialog", "modal_form"),
    (r"QGraphicsView|<canvas|canvas", "canvas_editor"),
    (r"QMainWindow|workbench|sidebar", "desktop_workbench"),
]


def _iter_sources(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        yield path


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _first_match(text: str, pattern: str) -> tuple[int, str] | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    return _line_of(text, match.start()), match.group(0)


def _archetype(text: str) -> tuple[str, float]:
    for pattern, archetype in ARCHETYPE_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return archetype, 0.8
    return "consumer_view", 0.5


def discover(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValueError(f"not a directory: {root_path}")
    pages: list[dict[str, Any]] = []
    anchors: list[str] = []
    capability_hits: dict[str, dict[str, Any]] = {}
    seen_routes: set[str] = set()
    component_meta: dict[str, tuple[str, float]] = {}

    for path in _iter_sources(root_path):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(root_path).as_posix()
        for testid in TESTID_RE.findall(text):
            if testid not in anchors:
                anchors.append(testid)
        for capability, patterns in CAPABILITY_PATTERNS.items():
            if capability in capability_hits:
                continue
            for pattern in patterns:
                hit = _first_match(text, pattern)
                if hit:
                    capability_hits[capability] = {"file": rel, "line": hit[0], "pattern": hit[1]}
                    break

        if path.name == "router.tsx" or path.name == "router.ts" or path.name == "routes.tsx":
            for route, component in ROUTE_RE.findall(text):
                if route in seen_routes:
                    continue
                seen_routes.add(route)
                line = _line_of(text, text.find(route))
                page_id = route.strip("/").replace("/", "-").replace(":", "") or component
                archetype, confidence = component_meta.get(component, _archetype(text))
                pages.append(
                    {
                        "page_id": page_id,
                        "kind": "route",
                        "route": route,
                        "source": {"file": rel, "line": line},
                        "archetype": archetype,
                        "confidence": confidence,
                        "capabilities": [],
                    }
                )
            continue

        for name in EXPORT_FN_RE.findall(text):
            if name in seen_routes:
                continue
            kind = "page"
            lower = text.lower()
            if "role=\"dialog\"" in lower or name.lower().endswith("dialog"):
                kind = "dialog"
            elif "modal" in lower:
                kind = "modal"
            archetype, confidence = _archetype(text)
            component_meta[name] = (archetype, confidence)
            page = {
                "page_id": name,
                "kind": kind,
                "route": f"component:{name}",
                "source": {"file": rel, "line": _line_of(text, text.find(name))},
                "archetype": archetype,
                "confidence": confidence,
                "capabilities": [],
            }
            if name not in {page["page_id"] for page in pages}:
                pages.append(page)

        if path.suffix.lower() == ".ui":
            for cls, widget_class, widget_name in CLASS_RE.findall(text):
                name = cls or widget_name
                if not name or name in seen_routes:
                    continue
                seen_routes.add(name)
                kind = "window" if widget_class == "QMainWindow" or cls else "panel"
                archetype, confidence = _archetype(text)
                pages.append(
                    {
                        "page_id": name,
                        "kind": kind,
                        "route": f"qt:{name}",
                        "source": {"file": rel, "line": _line_of(text, text.find(name))},
                        "archetype": archetype,
                        "confidence": confidence,
                        "capabilities": [],
                    }
                )

    if not pages:
        pages.append(
            {
                "page_id": root_path.name or "root",
                "kind": "page",
                "route": "/",
                "source": {"file": ".", "line": 1},
                "archetype": "consumer_view",
                "confidence": 0.2,
                "capabilities": [],
            }
        )

    capabilities = {name: name in capability_hits for name in CAPABILITY_PATTERNS}
    capability_evidence = [
        {
            "capability": capability,
            "source": {"kind": "file", "ref": hit["file"], "locator": f"line {hit['line']}"},
            "discovery": "static",
            "confidence": 0.7,
            "detail": hit["pattern"],
        }
        for capability, hit in capability_hits.items()
    ]
    contract_source = (root_path / "flows.json").is_file()
    sources = [
        {"source": "source", "status": "OBSERVED", "evidence_refs": list(dict.fromkeys(page["source"]["file"] for page in pages[:5]))},
        {"source": "runtime", "status": "UNVERIFIED", "detail": "no runtime probe in Stage 2"},
        {"source": "contract", "status": "OBSERVED" if contract_source else "MISSING", "detail": "flows.json" if contract_source else "no flows.json"},
    ]
    unverified_paths = [f"runtime:{page['page_id']}" for page in pages]
    report = {
        "schema_version": "1.3.3",
        "view_id": root_path.name or "root",
        "generated_at": "2026-10-24T00:00:00+00:00",
        "sources": sources,
        "pages": pages,
        "capabilities": capabilities,
        "capability_evidence": capability_evidence,
        "unverified_paths": unverified_paths,
    }
    errors = contracts.validation_errors("discovery", report)
    if errors:
        raise ValueError("; ".join(errors))
    return report


def flows_from_discovery(discovery: dict[str, Any]) -> dict[str, Any]:
    capabilities = discovery["capabilities"]
    states = ["list"]
    if capabilities.get("async_load"):
        states += ["loading", "error", "retry"]
    if capabilities.get("collection_display"):
        states.append("empty")
    if capabilities.get("user_mutation"):
        states.append("draft")
    if capabilities.get("long_running_task"):
        states.append("progress")
    if capabilities.get("destructive_operations"):
        states.append("saved")
    tasks = []
    for page in discovery["pages"]:
        tasks.append(
            {
                "task_id": page["page_id"],
                "actor_goal": f"use {page['page_id']}",
                "entry_point": "list",
                "steps": [page["route"]],
                "states": list(dict.fromkeys(states)),
                "runtime_assertions": [
                    {
                        "assertion_id": f"{page['page_id']}-entry",
                        "description": f"{page['page_id']} is reachable",
                        "expected_states": ["list"],
                    }
                ],
                "destructive_operations": [],
            }
        )
    flows = {
        "schema_version": "1.3.3",
        "view_id": discovery["view_id"],
        "view_archetype": discovery["pages"][0]["archetype"],
        "capabilities": capabilities,
        "capability_evidence": discovery["capability_evidence"],
        "tasks": tasks,
        "ui_anchors": [{"semantic_id": page["page_id"], "testid": None, "selector": page["route"]} for page in discovery["pages"]],
    }
    errors = contracts.validation_errors("flows", flows)
    if errors:
        raise ValueError("; ".join(errors))
    return flows


def rule_ids() -> list[str]:
    return [rule["rule_id"] for rule in rules.load_catalog()["rules"]]
