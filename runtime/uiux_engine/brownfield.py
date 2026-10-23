"""Brownfield design-token adoption and conflict priority (T2.6/M12)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import contracts, design_system, token_compiler

VAR_RE = re.compile(r"--([a-zA-Z0-9-]+)\s*:\s*([^;{}]+);")
SOURCE_SUFFIXES = {".css", ".qss", ".tsx", ".ts", ".scss"}
SAFETY_PAIRS = [("color-fg-primary", "color-bg-canvas")]


def _hex(value: str) -> tuple[int, int, int] | None:
    value = value.strip().lower()
    match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", value)
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        channel = value / 255
        channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first: str, second: str) -> float | None:
    one, two = _hex(first), _hex(second)
    if not one or not two:
        return None
    high, low = sorted((_luminance(one), _luminance(two)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 3)


def extract_existing(root: str | Path) -> dict[str, str]:
    root_path = Path(root)
    found: dict[str, str] = {}
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, value in VAR_RE.findall(text):
            found.setdefault(name, value.strip())
    return found


def suite_variables(tokens: dict[str, Any] | None = None) -> dict[str, str]:
    css = token_compiler.to_css(tokens)
    return {name: value.strip() for name, value in VAR_RE.findall(css)}


def build_report(project_root: str | Path, tokens: dict[str, Any] | None = None) -> dict[str, Any]:
    tokens = tokens or design_system.load_tokens()
    existing = extract_existing(project_root)
    suite = suite_variables(tokens)
    entries: list[dict[str, Any]] = []
    names = sorted(set(existing) | set(suite))
    for name in names:
        project_value = existing.get(name)
        suite_value = suite.get(name)
        if project_value is None:
            entries.append(
                {"name": name, "suite_value": suite_value, "existing_value": None, "action": "ADOPT", "priority": "SUITE", "rationale": "missing locally"}
            )
        elif suite_value is None:
            entries.append(
                {"name": name, "suite_value": None, "existing_value": project_value, "action": "KEEP_LOCAL", "priority": "PROJECT", "rationale": "local-only token"}
            )
        elif project_value == suite_value:
            entries.append(
                {"name": name, "suite_value": suite_value, "existing_value": project_value, "action": "KEEP_LOCAL", "priority": "PROJECT", "rationale": "already aligned"}
            )
        else:
            entries.append(
                {"name": name, "suite_value": suite_value, "existing_value": project_value, "action": "OVERRIDE", "priority": "PROJECT", "rationale": "local value wins for brand continuity"}
            )
    # Accessibility safety override: local fg/bg pairs below 4.5 must be flagged.
    local = {entry["name"]: entry["existing_value"] for entry in entries if entry["existing_value"]}
    for fg, bg in SAFETY_PAIRS:
        ratio = contrast(local.get(fg, ""), local.get(bg, ""))
        if ratio is not None and ratio < 4.5:
            for entry in entries:
                if entry["name"] in (fg, bg):
                    entry["action"] = "CONFLICT"
                    entry["priority"] = "SUITE"
                    entry["rationale"] = f"local contrast {ratio}:1 < 4.5; safety rule wins"
    summary = {
        "adopted": sum(entry["action"] == "ADOPT" for entry in entries),
        "overridden": sum(entry["action"] == "OVERRIDE" for entry in entries),
        "kept": sum(entry["action"] == "KEEP_LOCAL" for entry in entries),
        "conflicts": sum(entry["action"] == "CONFLICT" for entry in entries),
    }
    report = {
        "schema_version": "1.3.3",
        "project_id": Path(project_root).name or "project",
        "generated_at": "2026-10-24T00:00:00+00:00",
        "entries": entries,
        "summary": summary,
    }
    errors = contracts.validation_errors("brownfield-report", report)
    if errors:
        raise ValueError("; ".join(errors))
    report["ok"] = summary["conflicts"] == 0
    return report
