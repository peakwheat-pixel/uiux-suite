"""JSON Schema loading, validation and canonical hashing (V1.3.4, dual-version).

V1.3.3 contracts are frozen history and remain loadable; V1.3.4 adds a version
dispatch layer. Rules:

- Every schema set is self-contained per version (``*.v1.3.3.schema.json`` /
  ``*.v1.3.4.schema.json``); a v1.3.4 document never references v1.3.3 ids.
- The schema version is inferred from the instance's ``schema_version`` field.
- An instance without a version is validated against the current version, which
  fails closed because ``schema_version`` is required by every object schema.
- Unknown versions are rejected explicitly (``SCHEMA_VERSION_UNSUPPORTED``).
- Mixed-version finalize inputs are rejected (``SCHEMA_VERSION_MISMATCH``).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .enums import CONTRACTS_DIR

CURRENT_SCHEMA_VERSION = "1.3.4"
SUPPORTED_SCHEMA_VERSIONS = ("1.3.3", "1.3.4")


def schema_files(version: str = CURRENT_SCHEMA_VERSION) -> dict[str, str]:
    """Map schema stem -> filename for one contract version."""
    suffix = f".v{version}.schema.json"
    return {
        path.name[: -len(suffix)]: path.name
        for path in sorted(CONTRACTS_DIR.glob(f"*.v{version}.schema.json"))
    }


# Back-compatible alias: external code historically imported SCHEMA_FILES.
SCHEMA_FILES: dict[str, str] = schema_files(CURRENT_SCHEMA_VERSION)

_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$"
)


def _is_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if not _DATETIME_RE.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _format_checker() -> FormatChecker:
    checker = FormatChecker()
    checker.checks("date-time")(_is_datetime)
    return checker


@lru_cache(maxsize=None)
def _bundle(version: str) -> tuple[Registry, dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"unsupported schema version: {version!r}")
    registry = Registry()
    by_id: dict[str, dict[str, Any]] = {}
    by_stem: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource]] = []
    for filename in schema_files(version).values():
        path = CONTRACTS_DIR / filename
        doc = json.loads(path.read_text(encoding="utf-8"))
        schema_id = doc.get("$id")
        if not schema_id:
            raise ValueError(f"{path.name}: missing $id")
        resources.append((schema_id, Resource.from_contents(doc, default_specification=DRAFT202012)))
        by_id[schema_id] = doc
        by_stem[filename.split(f".v{version}")[0]] = doc
    registry = registry.with_resources(resources)
    return registry, by_id, by_stem


def _resolve_version(instance: Any, version: str | None) -> tuple[str | None, list[str]]:
    """Return (version, problems). Auto-detects from the instance."""
    if version is not None:
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            return None, [f"$: SCHEMA_VERSION_UNSUPPORTED: {version!r}"]
        return version, []
    detected = None
    if isinstance(instance, dict):
        raw = instance.get("schema_version")
        if isinstance(raw, str):
            detected = raw
    if detected is None:
        # fail closed downstream: every object schema requires schema_version
        return CURRENT_SCHEMA_VERSION, []
    if detected not in SUPPORTED_SCHEMA_VERSIONS:
        return None, [f"$: SCHEMA_VERSION_UNSUPPORTED: {detected!r}"]
    return detected, []


def schema_document(name: str, version: str = CURRENT_SCHEMA_VERSION) -> dict[str, Any]:
    _, by_id, by_stem = _bundle(version)
    files = schema_files(version)
    if name in files:
        filename = files[name]
        for schema_id, doc in by_id.items():
            if schema_id.endswith("/" + filename):
                return doc
    if name in by_stem:
        return by_stem[name]
    for doc in by_id.values():
        if doc.get("$id", "").endswith(name):
            return doc
    raise KeyError(f"schema not found: {name} (version {version})")


@lru_cache(maxsize=None)
def validator_for(name: str, version: str = CURRENT_SCHEMA_VERSION) -> Draft202012Validator:
    registry, _, _ = _bundle(version)
    return Draft202012Validator(
        schema_document(name, version),
        registry=registry,
        format_checker=_format_checker(),
    )


def validation_errors(
    name: str,
    instance: Any,
    version: str | None = None,
) -> list[str]:
    resolved, problems = _resolve_version(instance, version)
    if resolved is None:
        return problems
    errors = sorted(
        validator_for(name, resolved).iter_errors(instance),
        key=lambda e: list(e.absolute_path),
    )
    out: list[str] = []
    for err in errors:
        location = "$" + "".join(
            f"[{part!r}]" if isinstance(part, str) else f"[{part}]" for part in err.absolute_path
        )
        out.append(f"{location}: {err.message}")
    return out


def fragment_errors(
    schema_name: str,
    def_name: str,
    instance: Any,
    version: str | None = None,
) -> list[str]:
    resolved, problems = _resolve_version(instance, version)
    if resolved is None:
        return problems
    registry, _, _ = _bundle(resolved)
    wrapped = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"https://uiux-suite.local/contracts/{schema_files(resolved)[schema_name]}#/$defs/{def_name}",
    }
    validator = Draft202012Validator(wrapped, registry=registry, format_checker=_format_checker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{list(err.absolute_path)}: {err.message}" for err in errors]


def schema_files_for(version: str) -> dict[str, str]:
    """Public accessor mirroring SCHEMA_FILES for an explicit version."""
    return schema_files(version)


def is_valid(name: str, instance: Any, version: str | None = None) -> bool:
    return not validation_errors(name, instance, version)


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(data: Any) -> str:
    return sha256_bytes(canonical_json_bytes(data))


def version_consistency_errors(
    expected: str,
    documents: dict[str, Any],
    *,
    require_declared: bool = True,
) -> list[str]:
    """Fail closed on mixed/missing contract versions across finalize inputs."""
    problems: list[str] = []
    if expected not in SUPPORTED_SCHEMA_VERSIONS:
        return [f"SCHEMA_VERSION_UNSUPPORTED: {expected!r}"]
    for label, doc in documents.items():
        if isinstance(doc, list):
            items = doc
        else:
            items = [doc]
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            declared = item.get("schema_version")
            if declared is None:
                if require_declared:
                    problems.append(f"{label}[{index}]: SCHEMA_VERSION_MISSING")
                continue
            if declared not in SUPPORTED_SCHEMA_VERSIONS:
                problems.append(f"{label}[{index}]: SCHEMA_VERSION_UNSUPPORTED {declared!r}")
            elif declared != expected:
                problems.append(
                    f"{label}[{index}]: SCHEMA_VERSION_MISMATCH expected {expected!r} got {declared!r}"
                )
    return problems


def collect_enum_values(
    schema_name: str,
    version: str = CURRENT_SCHEMA_VERSION,
) -> list[tuple[str, tuple[str, ...]]]:
    found: list[tuple[str, tuple[str, ...]]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("enum"), list):
                found.append((path, tuple(node["enum"])))
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}/{index}")

    walk(schema_document(schema_name, version), "$")
    return found


def all_schema_enum_values() -> Iterable[tuple[str, str, tuple[str, ...]]]:
    for name in SCHEMA_FILES:
        for path, vals in collect_enum_values(name):
            yield name, path, vals
