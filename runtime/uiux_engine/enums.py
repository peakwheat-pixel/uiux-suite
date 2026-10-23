"""Canonical enum dictionary access for the UIUX engine (V1.3.3)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

PACKAGE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = PACKAGE_DIR.parent
SUITE_ROOT = RUNTIME_DIR.parent
CONTRACTS_DIR = SUITE_ROOT / "contracts"
ENUMS_PATH = CONTRACTS_DIR / "enums.v1.3.3.json"


@lru_cache(maxsize=1)
def load_enums() -> dict[str, Any]:
    with ENUMS_PATH.open("r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema_version") != "1.3.3":
        raise ValueError(f"unexpected enum dictionary version: {doc.get('schema_version')!r}")
    return doc


def enum_names() -> tuple[str, ...]:
    return tuple(load_enums()["enums"].keys())


def values(name: str) -> tuple[str, ...]:
    try:
        return tuple(load_enums()["enums"][name]["values"])
    except KeyError as exc:
        raise KeyError(f"unknown enum {name!r}; known: {', '.join(enum_names())}") from exc


def is_valid(name: str, value: Any) -> bool:
    return value in values(name)


def require(name: str, value: Any) -> str:
    if not is_valid(name, value):
        raise ValueError(f"{value!r} is not a valid {name}; expected one of {values(name)}")
    return value


def rank(name: str, value: str) -> int:
    table = load_enums()["enums"][name].get("rank")
    if table is None:
        raise KeyError(f"enum {name!r} has no rank order")
    return int(table[value])


def at_least(name: str, value: str, minimum: str) -> bool:
    return rank(name, value) >= rank(name, minimum)


def reason_codes() -> set[str]:
    return {entry["code"] for entry in load_enums()["reason_codes"]}


def reason_groups() -> dict[str, str]:
    return {entry["code"]: entry["group"] for entry in load_enums()["reason_codes"]}


def mapping(name: str) -> dict[str, Any]:
    return dict(load_enums()["mappings"][name])


def all_reason_codes_valid(codes: Iterable[str]) -> bool:
    known = reason_codes()
    return all(code in known for code in codes)


def self_check() -> list[str]:
    """Return a list of structural problems in the dictionary itself."""
    problems: list[str] = []
    doc = load_enums()
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
