"""JSON Schema loading, validation and canonical hashing (V1.3.3)."""
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

SCHEMA_FILES: dict[str, str] = {
    "common": "common.v1.3.3.schema.json",
    "task-request": "task-request.v1.3.3.schema.json",
    "task-result": "task-result.v1.3.3.schema.json",
    "gate-results": "gate-results.v1.3.3.schema.json",
    "coverage-matrix": "coverage-matrix.v1.3.3.schema.json",
    "evidence-manifest": "evidence-manifest.v1.3.3.schema.json",
    "tool-log": "tool-log.v1.3.3.schema.json",
    "review-attestation": "review-attestation.v1.3.3.schema.json",
    "design-review": "design-review.v1.3.3.schema.json",
    "suite-link": "suite-link.v1.3.3.schema.json",
    "release-manifest": "release-manifest.v1.3.3.schema.json",
    "policy": "policy.v1.3.3.schema.json",
    "host-capability": "host-capability.v1.3.3.schema.json",
    "flows": "flows.v1.3.3.schema.json",
    "rule-catalog": "rule-catalog.v1.3.3.schema.json",
    "rule-exemption": "rule-exemption.v1.3.3.schema.json",
}


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


@lru_cache(maxsize=1)
def _bundle() -> tuple[Registry, dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    registry = Registry()
    by_id: dict[str, dict[str, Any]] = {}
    by_stem: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource]] = []
    for path in sorted(CONTRACTS_DIR.glob("*.schema.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        schema_id = doc.get("$id")
        if not schema_id:
            raise ValueError(f"{path.name}: missing $id")
        resources.append((schema_id, Resource.from_contents(doc, default_specification=DRAFT202012)))
        by_id[schema_id] = doc
        by_stem[path.name.split(".v1.3.3")[0]] = doc
    registry = registry.with_resources(resources)
    return registry, by_id, by_stem


def schema_document(name: str) -> dict[str, Any]:
    _, by_id, by_stem = _bundle()
    if name in SCHEMA_FILES:
        filename = SCHEMA_FILES[name]
        for schema_id, doc in by_id.items():
            if schema_id.endswith("/" + filename):
                return doc
    if name in by_stem:
        return by_stem[name]
    for doc in by_id.values():
        if doc.get("$id", "").endswith(name):
            return doc
    raise KeyError(f"schema not found: {name}")


@lru_cache(maxsize=None)
def validator_for(name: str) -> Draft202012Validator:
    registry, _, _ = _bundle()
    return Draft202012Validator(
        schema_document(name),
        registry=registry,
        format_checker=_format_checker(),
    )


def validation_errors(name: str, instance: Any) -> list[str]:
    errors = sorted(validator_for(name).iter_errors(instance), key=lambda e: list(e.absolute_path))
    out: list[str] = []
    for err in errors:
        location = "$" + "".join(
            f"[{part!r}]" if isinstance(part, str) else f"[{part}]" for part in err.absolute_path
        )
        out.append(f"{location}: {err.message}")
    return out


def fragment_errors(schema_name: str, def_name: str, instance: Any) -> list[str]:
    """Validate an instance against one $defs entry of a bundled schema."""
    registry, _, _ = _bundle()
    wrapped = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"https://uiux-suite.local/contracts/{SCHEMA_FILES[schema_name]}#/$defs/{def_name}",
    }
    validator = Draft202012Validator(wrapped, registry=registry, format_checker=_format_checker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{list(err.absolute_path)}: {err.message}" for err in errors]


def is_valid(name: str, instance: Any) -> bool:
    return not validation_errors(name, instance)


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


def collect_enum_values(schema_name: str) -> list[tuple[str, tuple[str, ...]]]:
    """Collect every {"enum": [...]} inside a schema document (including $defs)."""
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

    walk(schema_document(schema_name), "$")
    return found


def all_schema_enum_values() -> Iterable[tuple[str, str, tuple[str, ...]]]:
    for name in SCHEMA_FILES:
        for path, vals in collect_enum_values(name):
            yield name, path, vals
