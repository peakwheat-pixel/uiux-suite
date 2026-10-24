"""Declarative test fixtures and environment preflight (TASK-01, V1.3.4).

Design rules:
- A fixture is data, not prose: roots, required environment, and synthetic data
  are declared and validated before any audit/test run.
- Environment problems are classified separately from product defects. An
  environment-authored failure must never be reported as a P0/P1 product bug.
- Fixtures only write inside the caller-provided sandbox root; real application
  data and source trees are never touched.
- Seven failure classes are first-class: fixture_invalid, missing_executable,
  missing_env, port_occupied, data_root_missing, readonly_violation,
  unsupported_stack.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path
from typing import Any

import jsonschema

PACKAGE_DIR = Path(__file__).resolve().parent
SUITE_ROOT = PACKAGE_DIR.parent.parent
FIXTURE_SCHEMA_PATH = SUITE_ROOT / "fixtures" / "schema" / "fixture.v1.schema.json"
FIXTURE_SCHEMA_VERSION = "1.0"

FAILURE_CLASSES = (
    "fixture_invalid",
    "missing_executable",
    "missing_env",
    "port_occupied",
    "data_root_missing",
    "readonly_violation",
    "unsupported_stack",
)

SUPPORTED_STACKS = {"tauri2-react-webview2", "electron", "web-spa", "qt", "winui", "wpf"}


class FixtureError(ValueError):
    """Raised when a fixture cannot be loaded, validated or applied."""


def _schema() -> dict[str, Any]:
    return json.loads(FIXTURE_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path)
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FixtureError(f"FIXTURE_INVALID: cannot read {fixture_path}: {exc}") from exc
    errors = sorted(jsonschema.Draft202012Validator(_schema()).iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        raise FixtureError(f"FIXTURE_INVALID: {list(first.absolute_path)}: {first.message}")
    problems = semantic_problems(payload)
    if problems:
        raise FixtureError("FIXTURE_INVALID: " + "; ".join(problems))
    return payload


def semantic_problems(fixture: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    project = fixture.get("project", {})
    if project.get("stack") not in SUPPORTED_STACKS:
        problems.append(f"unsupported_stack: {project.get('stack')!r}")
    roots = fixture.get("roots", {})
    if len({roots.get(key, "") for key in ("data_root", "derived_root", "catalog_db", "managed_root")}) != 4:
        problems.append("roots must be four distinct paths")
    for key, value in roots.items():
        if not value or "\x00" in value:
            problems.append(f"roots.{key} is empty or invalid")
    data = fixture.get("data", {})
    seen: set[str] = set()
    for item in data.get("files", []):
        rel = item["relative_path"]
        if rel in seen:
            problems.append(f"duplicate fixture file: {rel}")
        seen.add(rel)
        if item["content_kind"] == "json" and "payload" not in item:
            problems.append(f"{rel}: json content requires payload")
    if not data.get("files") and not data.get("entities"):
        problems.append("fixture declares neither files nor entities")
    return problems


def environment_facts() -> dict[str, Any]:
    import sys

    return {
        "os": "windows" if os.name == "nt" else ("macos" if sys.platform == "darwin" else "linux"),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "env": dict(os.environ),
        "executables": {},
        "ports": {},
        "free_gb": _free_gb(),
    }


def _free_gb() -> float:
    try:
        return round(shutil.disk_usage(SUITE_ROOT).free / (1024 ** 3), 2)
    except OSError:
        return 0.0


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def preflight_problems(
    fixture: dict[str, Any],
    facts: dict[str, Any] | None = None,
    sandbox_root: str | Path | None = None,
) -> list[dict[str, str]]:
    """Return classified environment problems. Empty list means preflight passed."""
    facts = facts or environment_facts()
    sandbox = Path(sandbox_root).resolve() if sandbox_root else None
    problems: list[dict[str, str]] = []

    problem = semantic_problems(fixture)
    for item in problem:
        problems.append({"class": "fixture_invalid", "code": "FIXTURE_INVALID", "detail": item})

    env = fixture.get("environment", {})
    expected_os = env.get("os", "any")
    if expected_os != "any" and facts.get("os") != expected_os:
        problems.append({
            "class": "unsupported_stack",
            "code": "OS_UNSUPPORTED",
            "detail": f"fixture requires {expected_os}, host is {facts.get('os')}",
        })

    if fixture["project"].get("stack") not in SUPPORTED_STACKS:
        problems.append({
            "class": "unsupported_stack",
            "code": "STACK_UNSUPPORTED",
            "detail": f"stack {fixture['project'].get('stack')!r} is not supported",
        })

    for entry in env.get("required_executables", []):
        path = entry["path"]
        if sandbox is not None:
            path = path.replace("<sandbox>", sandbox.as_posix())
        if not Path(path).is_file():
            problems.append({
                "class": "missing_executable",
                "code": "EXECUTABLE_MISSING",
                "detail": f"{entry['purpose']} executable not found: {path}",
            })

    for name in env.get("required_env", []):
        if name not in facts.get("env", {}):
            problems.append({
                "class": "missing_env",
                "code": "ENV_VAR_MISSING",
                "detail": f"required environment variable is not set: {name}",
            })

    for entry in env.get("ports", []):
        port = int(entry["port"])
        if facts.get("ports", {}).get(port) is None:
            busy = _port_open(port)
        else:
            busy = bool(facts["ports"][port])
        if entry["purpose"] == "cdp" and not busy:
            problems.append({
                "class": "port_occupied",
                "code": "CDP_PORT_NOT_LISTENING",
                "detail": f"expected CDP port {port} is not listening",
            })
        elif entry["purpose"] != "cdp" and busy:
            problems.append({
                "class": "port_occupied",
                "code": "PORT_OCCUPIED",
                "detail": f"port {port} ({entry['purpose']}) is already in use",
            })

    min_free = float(env.get("min_free_gb", 0) or 0)
    if min_free and facts.get("free_gb", 0) < min_free:
        problems.append({
            "class": "data_root_missing",
            "code": "DISK_SPACE_LOW",
            "detail": f"free space {facts.get('free_gb')}GB < required {min_free}GB",
        })

    for key in ("data_root", "derived_root", "catalog_db", "managed_root"):
        raw = fixture["roots"][key]
        if "<sandbox>" in raw and sandbox is None:
            problems.append({
                "class": "data_root_missing",
                "code": "SANDBOX_ROOT_UNRESOLVED",
                "detail": f"roots.{key} still contains <sandbox> placeholder",
            })

    return problems


def resolve_roots(fixture: dict[str, Any], sandbox_root: str | Path) -> dict[str, Path]:
    sandbox = Path(sandbox_root).resolve()
    resolved: dict[str, Path] = {}
    for key, raw in fixture["roots"].items():
        value = raw.replace("<sandbox>", sandbox.as_posix())
        path = Path(value).resolve()
        if sandbox not in path.parents and path != sandbox:
            raise FixtureError(f"READONLY_VIOLATION: roots.{key} escapes sandbox: {path}")
        resolved[key] = path
    return resolved


def apply_fixture(fixture: dict[str, Any], sandbox_root: str | Path) -> dict[str, Any]:
    """Materialise synthetic data inside the sandbox. Real data is untouched."""
    sandbox = Path(sandbox_root).resolve()
    sandbox.mkdir(parents=True, exist_ok=True)
    roots = resolve_roots(fixture, sandbox)
    for key, path in roots.items():
        if key == "catalog_db":
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
    applied: list[str] = []
    for item in fixture["data"].get("files", []):
        target = (sandbox / item["relative_path"]).resolve()
        if sandbox not in target.parents and target != sandbox:
            raise FixtureError(f"READONLY_VIOLATION: fixture file escapes sandbox: {target}")
        if item["content_kind"] == "dir":
            target.mkdir(parents=True, exist_ok=True)
            applied.append(target.relative_to(sandbox).as_posix() + "/")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if item["content_kind"] == "json":
            target.write_text(json.dumps(item.get("payload", {}), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            target.write_text(str(item.get("payload", "")), encoding="utf-8")
        applied.append(target.relative_to(sandbox).as_posix())
    catalog = fixture["data"].get("catalog_snapshot")
    if catalog:
        catalog_path = roots["catalog_db"]
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                {
                    "kind": catalog.get("kind", "json_snapshot"),
                    "fixture_id": fixture["fixture_id"],
                    "tables": catalog.get("tables", {}),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        applied.append(str(catalog_path))
    return {
        "fixture_id": fixture["fixture_id"],
        "sandbox_root": str(sandbox),
        "roots": {key: str(value) for key, value in roots.items()},
        "applied": sorted(applied),
        "entities": fixture["data"].get("entities", {}),
        "read_only": bool(fixture.get("read_only", True)),
    }


def classify_ab_attribution(
    *,
    bad_problems: list[dict[str, str]],
    good_problems: list[dict[str, str]],
    product_signal: bool = False,
) -> dict[str, Any]:
    """A/B control: environment-authored failures must not become product defects."""
    bad_classes = {item["class"] for item in bad_problems}
    good_classes = {item["class"] for item in good_problems}
    environment_only = bad_classes - good_classes
    environment_authored = bool(environment_only) and not product_signal
    return {
        "bad_classes": sorted(bad_classes),
        "good_classes": sorted(good_classes),
        "environment_only_classes": sorted(environment_only),
        "environment_authored": environment_authored,
        "product_defect_eligible": not environment_authored,
        "rule": (
            "if the bad run fails only on environment/fixture classes and the good "
            "control run is clean, the finding is an environment error (not P0/P1)"
            if environment_authored
            else "product signal or shared environment class; eligible for defect classification"
        ),
    }


def failure_class_matrix() -> list[dict[str, Any]]:
    """Deterministic self-description used by tests and the release gate."""
    return [
        {"class": "fixture_invalid", "detected_by": "load_fixture", "code": "FIXTURE_INVALID"},
        {"class": "missing_executable", "detected_by": "preflight_problems", "code": "EXECUTABLE_MISSING"},
        {"class": "missing_env", "detected_by": "preflight_problems", "code": "ENV_VAR_MISSING"},
        {"class": "port_occupied", "detected_by": "preflight_problems", "code": "PORT_OCCUPIED"},
        {"class": "data_root_missing", "detected_by": "preflight_problems", "code": "SANDBOX_ROOT_UNRESOLVED"},
        {"class": "readonly_violation", "detected_by": "resolve_roots/apply_fixture", "code": "READONLY_VIOLATION"},
        {"class": "unsupported_stack", "detected_by": "semantic_problems", "code": "STACK_UNSUPPORTED"},
    ]
