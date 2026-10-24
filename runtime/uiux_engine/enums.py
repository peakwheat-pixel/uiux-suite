"""Canonical enum dictionary access for the UIUX engine (V1.3.4, version-aware).

The dictionary is versioned with the contracts: ``enums.v1.3.3.json`` is frozen
history; ``enums.v1.3.4.json`` adds the disposition/delivery-dimension enums and
the new reason codes. The current engine reads the current version by default.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

PACKAGE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = PACKAGE_DIR.parent
SUITE_ROOT = RUNTIME_DIR.parent
CONTRACTS_DIR = SUITE_ROOT / "contracts"

CURRENT_ENUM_VERSION = "1.3.4"
SUPPORTED_ENUM_VERSIONS = ("1.3.3", "1.3.4")


def enums_path(version: str = CURRENT_ENUM_VERSION) -> Path:
    return CONTRACTS_DIR / f"enums.v{version}.json"


@lru_cache(maxsize=None)
def load_enums(version: str = CURRENT_ENUM_VERSION) -> dict[str, Any]:
    if version not in SUPPORTED_ENUM_VERSIONS:
        raise ValueError(f"unsupported enum dictionary version: {version!r}")
    with enums_path(version).open("r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema_version") != version:
        raise ValueError(f"unexpected enum dictionary version: {doc.get('schema_version')!r}")
    return doc


def enum_names(version: str = CURRENT_ENUM_VERSION) -> tuple[str, ...]:
    return tuple(load_enums(version)["enums"].keys())


def values(name: str, version: str = CURRENT_ENUM_VERSION) -> tuple[str, ...]:
    try:
        return tuple(load_enums(version)["enums"][name]["values"])
    except KeyError as exc:
        raise KeyError(f"unknown enum {name!r}; known: {', '.join(enum_names(version))}") from exc


def is_valid(name: str, value: Any, version: str = CURRENT_ENUM_VERSION) -> bool:
    return value in values(name, version)


def require(name: str, value: Any, version: str = CURRENT_ENUM_VERSION) -> str:
    if not is_valid(name, value, version):
        raise ValueError(f"{value!r} is not a valid {name}; expected one of {values(name, version)}")
    return value


def rank(name: str, value: str, version: str = CURRENT_ENUM_VERSION) -> int:
    table = load_enums(version)["enums"][name].get("rank")
    if table is None:
        raise KeyError(f"enum {name!r} has no rank order")
    return int(table[value])


def at_least(name: str, value: str, minimum: str, version: str = CURRENT_ENUM_VERSION) -> bool:
    return rank(name, value, version) >= rank(name, minimum, version)


def reason_codes(version: str = CURRENT_ENUM_VERSION) -> set[str]:
    return {entry["code"] for entry in load_enums(version)["reason_codes"]}


def reason_groups(version: str = CURRENT_ENUM_VERSION) -> dict[str, str]:
    return {entry["code"]: entry["group"] for entry in load_enums(version)["reason_codes"]}


def mapping(name: str, version: str = CURRENT_ENUM_VERSION) -> dict[str, Any]:
    return dict(load_enums(version)["mappings"][name])


def all_reason_codes_valid(codes: Iterable[str], version: str = CURRENT_ENUM_VERSION) -> bool:
    known = reason_codes(version)
    return all(code in known for code in codes)


def self_check(version: str = CURRENT_ENUM_VERSION) -> list[str]:
    """Return a list of structural problems in the dictionary itself."""
    problems: list[str] = []
    doc = load_enums(version)
    for name, spec in doc["enums"].items():
        vals = spec.get("values")
        if not isinstance(vals, list) or not vals or len(vals) != len(set(vals)):
            problems.append(f"enum {name}: values must be a non-empty unique list")
        ranks = spec.get("rank")
        if ranks is not None:
            if set(ranks) != set(vals):
                problems.append(f"enum {name}: rank keys do not match values")
    seen: set[str] = set()
    for entry in doc["reason_codes"]:
        code = entry["code"]
        if code in seen:
            problems.append(f"duplicate reason code: {code}")
        seen.add(code)
        if not entry.get("group"):
            problems.append(f"reason code {code}: missing group")
    return problems
