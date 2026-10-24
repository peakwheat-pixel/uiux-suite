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


# ---------------------------------------------------------------------------
# G1 full static discovery + inventory reconciliation (V1.3.5, TASK-02)
# ---------------------------------------------------------------------------
G1_VERSION = "1.3.5"
G1_FRONTEND_DIR = Path("apps/desktop/frontend/src")
G1_RUST_DIR = Path("apps/desktop/src-tauri/src")
G1_EXTS = {".tsx", ".ts", ".rs"}

RE_G1_DIALOG = re.compile(r'role="dialog"')
RE_G1_GAP = re.compile(r"GAP-G(\d+)")
RE_G1_DISABLED_FEATURE = re.compile(r'id="(gap-g\d+[a-z0-9-]*)"')
RE_G1_DISABLED_PROP = re.compile(r"\bdisabled\b")
RE_G1_ARIA = re.compile(r"\baria-[a-z-]+")
RE_G1_STATE_ENUM = re.compile(r"\b(?:enum|type|interface)\s+(\w*(?:Status|State|Phase)\w*)\b")
RE_G1_RUST_ENUM = re.compile(r"\bpub\s+enum\s+(\w+)")
RE_G1_TAURI_COMMAND = re.compile(r"#\[tauri::command\]")

G1_INVENTORY_SOURCE_MAP: dict[str, list[str]] = {
    "ITM-PAGE-READER": ["reader", "page-reader"],
    "ITM-PAGE-WORKBENCH": ["workbench", "page-workbench"],
    "ITM-PAGE-SEARCH": ["search", "page-search"],
    "ITM-PAGE-SETTINGS": ["settings", "page-settings"],
    "ITM-REGION-LIST": ["region", "region-list"],
    "ITM-REGION-EDIT": ["region", "inspector", "region-edit"],
    "ITM-TASK-STATES": ["taskprogress", "task-status", "run-status", "taskstate"],
    "ITM-IMPORT-FLOW": ["importdialog", "import"],
    "ITM-EXPORT-FLOW": ["exportdialog", "export"],
    "ITM-DIALOG-DELETE": ["deleteconfirm", "permanentdelete"],
    "ITM-DIALOG-IMPORT-CONFIRM": ["importdialog", "confirm"],
    "ITM-MENU-MAIN": ["appshell", "rail", "nav"],
    "ITM-CMD-PERMANENT-DELETE": ["permanentdelete", "delete"],
    "ITM-CMD-IMPORT-EXECUTE": ["import", "execute"],
    "ITM-ENTRY-DESKTOP": ["main.tsx", "tauri", "lib.rs"],
    "ITM-NATIVE-FILE-PICKER": ["dialog", "open", "file-picker", "picker"],
    "ITM-NATIVE-SAVE-DIALOG": ["save", "dialog"],
    "ITM-UIA-TREE": ["uia", "accessibility"],
}


def _g1_files(root: Path, directory: Path) -> list[Path]:
    base = root / directory
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file() and p.suffix in G1_EXTS)


def _g1_git(root: Path, *args: str) -> str:
    import subprocess

    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    return proc.stdout.strip()


def g1_source_binding(root: Path) -> dict[str, Any]:
    head = _g1_git(root, "rev-parse", "HEAD")
    lines = [line for line in _g1_git(root, "status", "--porcelain").splitlines() if line.strip()]
    business = [line for line in lines if "apps/" in line or "src/" in line]
    details = []
    import hashlib

    for line in business:
        rel = line[3:].strip()
        path = root / rel
        details.append({
            "status": line[:2].strip(),
            "path": rel,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        })
    return {
        "kind": "git_commit",
        "value": head or "unknown",
        "dirty": bool(lines),
        "dirty_lines": len(lines),
        "business_source_dirty": bool(business),
        "business_dirty_lines": business,
        "business_dirty_details": details,
    }


def discover_g1(source_root: str | Path) -> dict[str, Any]:
    """G1 full static discovery: pages/dialogs/entries/gaps/disabled/a11y/states."""
    import hashlib

    root = Path(source_root)
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    binding = g1_source_binding(root)
    files = _g1_files(root, G1_FRONTEND_DIR) + _g1_files(root, G1_RUST_DIR)
    tree_parts: list[tuple[str, str]] = []
    pages: dict[str, dict[str, Any]] = {}
    dialogs: dict[str, dict[str, Any]] = {}
    entries: dict[str, dict[str, Any]] = {}
    gaps: dict[str, dict[str, Any]] = {}
    disabled_features: dict[str, dict[str, Any]] = {}
    aria_attrs: set[str] = set()
    state_enums: set[str] = set()
    rust_commands = 0
    disabled_files: list[str] = []

    for path in files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        tree_parts.append((rel, digest))
        for match in TESTID_RE.finditer(text):
            testid = match.group(1)
            entries.setdefault(testid, {"testid": testid, "file": rel})
            page_match = re.match(r"page-([a-z0-9-]+)", testid)
            if page_match:
                pages.setdefault(page_match.group(1), {"page": page_match.group(1), "testid": testid, "file": rel})
        if RE_G1_DIALOG.search(text):
            dialog_id = path.stem.replace("Dialog", "").lower() or path.stem.lower()
            dialogs.setdefault(dialog_id, {"dialog": dialog_id, "file": rel,
                                           "testids": sorted(set(TESTID_RE.findall(text)))})
        for match in RE_G1_GAP.finditer(text):
            gaps.setdefault(f"GAP-G{match.group(1)}", {"gap": f"GAP-G{match.group(1)}", "file": rel})
        for match in RE_G1_DISABLED_FEATURE.finditer(text):
            disabled_features.setdefault(match.group(1), {"id": match.group(1), "file": rel})
        aria_attrs.update(RE_G1_ARIA.findall(text))
        state_enums.update(RE_G1_STATE_ENUM.findall(text))
        if path.suffix == ".rs":
            rust_commands += len(RE_G1_TAURI_COMMAND.findall(text))
            state_enums.update(f"rust:{name}" for name in RE_G1_RUST_ENUM.findall(text))
        if RE_G1_DISABLED_PROP.search(text):
            disabled_files.append(rel)

    tree_digest = hashlib.sha256()
    for rel, digest in sorted(tree_parts):
        tree_digest.update(rel.encode("utf-8"))
        tree_digest.update(b"\x00")
        tree_digest.update(bytes.fromhex(digest))
    return {
        "schema_version": G1_VERSION,
        "kind": "g1_static_discovery",
        "source_root": str(root),
        "source_binding": binding,
        "source_files": sorted(rel for rel, _digest in tree_parts),
        "scanned": {
            "files": len(files),
            "frontend_files": len(_g1_files(root, G1_FRONTEND_DIR)),
            "rust_files": len(_g1_files(root, G1_RUST_DIR)),
            "tree_digest": tree_digest.hexdigest(),
        },
        "pages": [pages[key] for key in sorted(pages)],
        "dialogs": [dialogs[key] for key in sorted(dialogs)],
        "entries": [entries[key] for key in sorted(entries)],
        "gaps": [gaps[key] for key in sorted(gaps)],
        "disabled_features": [disabled_features[key] for key in sorted(disabled_features)],
        "a11y": {"aria_attributes": sorted(aria_attrs), "count": len(aria_attrs)},
        "state_machines": sorted(state_enums),
        "rust_commands": rust_commands,
        "disabled_occurrences": {"files": sorted(disabled_files), "count": len(disabled_files)},
        "summary": {
            "pages": len(pages),
            "dialogs": len(dialogs),
            "entries": len(entries),
            "gaps": len(gaps),
            "disabled_features": len(disabled_features),
            "state_machines": len(state_enums),
        },
        "note": "static discovery only; runtime and verification states are not inferred",
    }


def _g1_evidence(needle: str, discovery: dict[str, Any]) -> list[str]:
    haystack: list[str] = []
    for collection in ("pages", "dialogs", "gaps", "disabled_features"):
        for row in discovery.get(collection, []):
            haystack.extend(str(value).lower() for value in row.values())
    haystack.extend(str(row.get("testid", "")).lower() for row in discovery.get("entries", []))
    haystack.extend(str(name).lower() for name in discovery.get("state_machines", []))
    haystack.extend(str(name).lower() for name in discovery.get("source_files", []))
    return sorted({value for value in haystack if needle in value})[:5]


def reconcile_inventory(discovery: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for item in inventory.get("items", []):
        stable_id = str(item.get("stable_id"))
        needles = G1_INVENTORY_SOURCE_MAP.get(stable_id, [stable_id.lower()])
        evidence: list[str] = []
        for needle in needles:
            evidence.extend(_g1_evidence(needle.lower(), discovery))
        found = bool(evidence)
        declared = item.get("declared_scope")
        if declared == "excluded":
            state = "EXCLUDED_DECLARED"
        elif found:
            state = "IMPLEMENTED_FOUND"
        else:
            state = "NOT_FOUND_IN_SOURCE"
        results.append({
            "stable_id": stable_id,
            "declared_scope": declared,
            "risk_level": item.get("risk_level"),
            "state": state,
            "evidence": evidence,
        })
    return {
        "schema_version": G1_VERSION,
        "kind": "inventory_reconciliation",
        "inventory_items": len(inventory.get("items", [])),
        "found": len([r for r in results if r["state"] == "IMPLEMENTED_FOUND"]),
        "not_found": len([r for r in results if r["state"] == "NOT_FOUND_IN_SOURCE"]),
        "excluded_declared": len([r for r in results if r["state"] == "EXCLUDED_DECLARED"]),
        "items": results,
        "discovered_entities_not_in_inventory": [
            {"kind": "dialog", **row} for row in discovery.get("dialogs", [])
        ] + [
            {"kind": "gap", **row} for row in discovery.get("gaps", [])
        ],
        "note": "static discovery evidence only; it never upgrades verification state",
    }


def freeze_discovery(discovery: dict[str, Any]) -> str:
    import hashlib
    import json

    canonical = json.dumps(discovery, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
