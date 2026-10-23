"""Deterministic style-token linter (Stage 1 / T1.2).

Static, read-only screening for CSS/QSS and optional HTML/TSX style fragments.
Standard library only. Rule IDs and severities are read from the frozen catalog
(``knowledge/rules/catalog.v1.0.json``); this module never invents either.

Coverage note: the frozen catalog assigns several of the rules covered here to
the ``accessibility_checker`` detector. This linter implements the deterministic
*static* subset of those rules and reports them with the catalog's own rule ID
and severity so downstream gates consume a single ID space. Results are regex /
lightweight-parser screening, not an AST proof (SPEC V1.3.3 section 7).

Unknown background colors, relative units that cannot be resolved, and any
other non-decidable input are skipped instead of guessed: silence means
"not statically proven", not "clean".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import rules
from .enums import SUITE_ROOT

LINTER_VERSION = "1.0"
DETECTOR = "style_token_linter"
SUPPORTED_STACKS = ("web", "qt")

# Static subset of the frozen catalog. Every ID is checked against the catalog
# at emission time; severities always come from the catalog entry.
SUPPORTED_RULE_IDS = (
    "UX-COLOR-001",
    "UX-COLOR-002",
    "UX-TYPE-001",
    "UX-TYPE-002",
    "UX-SPACE-001",
    "UX-A11Y-001",
    "UX-A11Y-003",
    "UX-A11Y-004",
    "UX-COPY-001",
    "UX-MOTION-001",
)

_SPACING_GRID_PX = 4.0
_MIN_FONT_SIZE_PX = 12.0
_MIN_LINE_HEIGHT = 1.3
_CONTRAST_NORMAL = 4.5
_CONTRAST_LARGE = 3.0
_LARGE_TEXT_PX = 24.0
_LARGE_BOLD_TEXT_PX = 18.66

_SEVERITIES = ("FAIL", "WARNING", "INFO")


# ---------------------------------------------------------------------------
# Frozen catalog access
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _catalog_index() -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in rules.load_catalog()["rules"]}


def _catalog_version() -> str:
    return str(rules.load_catalog().get("catalog_version"))


def _rule_severity(rule_id: str) -> str:
    """Return the catalog severity for ``rule_id`` or raise; never invent one."""
    rule = _catalog_index().get(rule_id)
    if rule is None:
        raise KeyError(f"rule_id is not in the frozen catalog: {rule_id}")
    if not rule.get("enabled", True):
        raise ValueError(f"rule is disabled in the frozen catalog: {rule_id}")
    severity = rule["severity"]
    if severity not in _SEVERITIES:
        raise ValueError(f"catalog severity is not a RuleSeverity value: {severity!r}")
    return severity


def catalog_bindings() -> list[str]:
    """Return problems binding :data:`SUPPORTED_RULE_IDS` to the frozen catalog."""
    problems: list[str] = []
    for rule_id in SUPPORTED_RULE_IDS:
        try:
            _rule_severity(rule_id)
        except (KeyError, ValueError) as exc:
            problems.append(str(exc))
    return problems


def supported_rules() -> list[dict[str, str]]:
    """Describe the catalog binding of every rule this linter can emit."""
    out: list[dict[str, str]] = []
    for rule_id in SUPPORTED_RULE_IDS:
        rule = _catalog_index()[rule_id]
        out.append(
            {
                "rule_id": rule_id,
                "severity": _rule_severity(rule_id),
                "title": str(rule.get("title", "")),
                "detector": str(rule.get("detector", "")),
            }
        )
    return out


def _finding(
    rule_id: str,
    file: str,
    line: int,
    message: str,
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "rule_id": rule_id,
        "severity": _rule_severity(rule_id),
        "file": file,
        "line": int(max(1, line)),
        "message": message,
    }
    if evidence_ref:
        finding["evidence_ref"] = evidence_ref
    return finding


# ---------------------------------------------------------------------------
# Style sheet model and CSS/QSS parsing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Declaration:
    prop: str
    value: str
    line: int
    selector: str
    block_id: int
    contexts: tuple[str, ...] = ()


class StyleSheet:
    """Flat declaration list with block ids; nested at-rules stay in contexts."""

    def __init__(self) -> None:
        self.declarations: list[Declaration] = []
        self._next_block = 0

    def new_block(self) -> int:
        self._next_block += 1
        return self._next_block

    def add(
        self,
        prop: str,
        value: str,
        line: int,
        selector: str,
        block_id: int,
        contexts: tuple[str, ...] = (),
    ) -> None:
        self.declarations.append(Declaration(prop, value, line, selector, block_id, contexts))

    def merge(self, other: "StyleSheet") -> None:
        mapping: dict[int, int] = {}
        for declaration in other.declarations:
            block_id = mapping.setdefault(declaration.block_id, self.new_block())
            self.declarations.append(
                Declaration(
                    declaration.prop,
                    declaration.value,
                    declaration.line,
                    declaration.selector,
                    block_id,
                    declaration.contexts,
                )
            )


_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def _strip_comments(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return _COMMENT_RE.sub(_replace, text)


def _find_matching_brace(text: str, open_idx: int, end: int) -> int:
    depth = 0
    index = open_idx
    while index < end:
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _emit_declaration(
    sheet: StyleSheet,
    text: str,
    start: int,
    end: int,
    selector: str,
    block_id: int,
    contexts: tuple[str, ...],
    line_offset: int,
) -> None:
    raw = text[start:end]
    if not raw.strip() or ":" not in raw:
        return
    stripped = raw.strip()
    prop, _, value = stripped.partition(":")
    prop = prop.strip().lower()
    value = value.strip()
    if not prop or not value or prop.startswith("@"):
        return
    leading = len(raw) - len(raw.lstrip())
    line = line_offset + text.count("\n", 0, start + leading) + 1
    sheet.add(prop, value, line, selector, block_id, contexts)


def _walk_block_content(
    sheet: StyleSheet,
    text: str,
    start: int,
    end: int,
    selector: str,
    block_id: int,
    contexts: tuple[str, ...],
    line_offset: int,
) -> None:
    index = start
    decl_start = start
    while index < end:
        char = text[index]
        if char == ";":
            _emit_declaration(sheet, text, decl_start, index, selector, block_id, contexts, line_offset)
            decl_start = index + 1
        elif char == "{":
            nested_selector = " ".join(text[decl_start:index].split())
            nested_close = _find_matching_brace(text, index, end)
            if nested_close == -1:
                return
            if not nested_selector:
                index = nested_close + 1
                decl_start = index
                continue
            if nested_selector.startswith("@"):
                nested_contexts = contexts + (nested_selector,)
                full_selector = nested_selector
            else:
                nested_contexts = contexts
                full_selector = nested_selector if not selector or selector.startswith("@") else f"{selector} {nested_selector}"
            nested_block = sheet.new_block()
            _walk_block_content(
                sheet,
                text,
                index + 1,
                nested_close,
                full_selector,
                nested_block,
                nested_contexts,
                line_offset,
            )
            index = nested_close + 1
            decl_start = index
            continue
        index += 1
    if decl_start < end:
        _emit_declaration(sheet, text, decl_start, end, selector, block_id, contexts, line_offset)


def _walk_top_level(
    sheet: StyleSheet,
    text: str,
    start: int,
    end: int,
    contexts: tuple[str, ...],
    line_offset: int,
) -> None:
    index = start
    while index < end:
        while index < end and text[index] in " \t\r\n;}":
            index += 1
        if index >= end:
            break
        open_idx = text.find("{", index, end)
        if open_idx == -1:
            break
        close_idx = _find_matching_brace(text, open_idx, end)
        if close_idx == -1:
            break
        selector = " ".join(text[index:open_idx].split())
        block_contexts = contexts + (selector,) if selector.startswith("@") else contexts
        block_id = sheet.new_block()
        _walk_block_content(
            sheet,
            text,
            open_idx + 1,
            close_idx,
            selector,
            block_id,
            block_contexts,
            line_offset,
        )
        index = close_idx + 1


def parse_css(text: str, *, line_offset: int = 0) -> StyleSheet:
    """Parse CSS/QSS text into declarations with 1-based line numbers."""
    clean = _strip_comments(text)
    sheet = StyleSheet()
    _walk_top_level(sheet, clean, 0, len(clean), (), line_offset)
    return sheet


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------
_IMPORTANT_RE = re.compile(r"\s*!\s*important\s*$", re.I)
_NUMBER_UNIT_RE = re.compile(r"^(-?\d*\.?\d+)\s*(px|pt|rem|em)?$", re.I)
_ANIMATION_TIME_RE = re.compile(r"(?<![\w.])(\d*\.?\d+)\s*(ms|s)\b", re.I)


def _strip_important(value: str) -> str:
    return _IMPORTANT_RE.sub("", value.strip()).strip()


def _length_px(value: str) -> float | None:
    match = _NUMBER_UNIT_RE.match(_strip_important(value).lower())
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    if unit == "px":
        return amount
    if unit == "pt":
        return amount * 4.0 / 3.0
    if unit in ("rem", "em"):
        # Relative to the assumed 16px root / inherited font size; documented
        # as a static approximation in docs/STYLE_LINTER.md.
        return amount * 16.0
    return None


def _font_size_px(block: Sequence[Declaration]) -> float | None:
    for declaration in block:
        if declaration.prop == "font-size":
            px = _length_px(declaration.value)
            if px is not None:
                return px
    return None


def _font_weight(block: Sequence[Declaration]) -> int:
    for declaration in block:
        if declaration.prop != "font-weight":
            continue
        value = _strip_important(declaration.value).lower()
        if value in ("bold", "bolder"):
            return 700
        if value in ("normal", "lighter"):
            return 400
        if value.isdigit():
            return int(value)
    return 400


_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "maroon": (128, 0, 0),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "olive": (128, 128, 0),
    "lime": (0, 255, 0),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
}
_RGB_RE = re.compile(r"rgba?\(\s*([^)]*)\)", re.I)
_HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*))?\)")


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    length = len(value)
    try:
        if length in (3, 4):
            red, green, blue = (int(value[i] * 2, 16) for i in range(3))
            alpha = int(value[3] * 2, 16) if length == 4 else 255
        elif length in (6, 8):
            red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
            alpha = int(value[6:8], 16) if length == 8 else 255
        else:
            return None
    except ValueError:
        return None
    if alpha < 255:
        return None
    return red, green, blue


def _parse_rgb_color(args: str) -> tuple[int, int, int] | None:
    if "," in args:
        parts = [part.strip() for part in args.split(",")]
        channels = parts[:3]
        alpha_text = parts[3] if len(parts) > 3 else None
    else:
        slash_parts = args.split("/", 1)
        channels = slash_parts[0].split()
        alpha_text = slash_parts[1].strip() if len(slash_parts) > 1 else None
    if len(channels) < 3:
        return None
    if alpha_text is not None:
        alpha_text = alpha_text.strip()
        try:
            alpha = float(alpha_text[:-1]) / 100.0 if alpha_text.endswith("%") else float(alpha_text)
        except ValueError:
            return None
        if alpha < 1.0:
            return None
    values: list[int] = []
    for channel in channels[:3]:
        try:
            if channel.endswith("%"):
                values.append(max(0, min(255, round(float(channel[:-1]) * 2.55))))
            else:
                values.append(max(0, min(255, round(float(channel)))))
        except ValueError:
            return None
    return values[0], values[1], values[2]


def _extract_color(value: str) -> tuple[int, int, int] | None:
    raw = _strip_important(value)
    if not raw:
        return None
    lowered = raw.lower()
    if "gradient" in lowered:
        return None
    match = _RGB_RE.search(raw)
    if match:
        return _parse_rgb_color(match.group(1))
    match = _HEX_COLOR_RE.search(raw)
    if match:
        return _parse_hex_color(match.group(1))
    if "url(" in lowered or "transparent" in lowered:
        return None
    tokens = lowered.replace(",", " ").split()
    for token in tokens[:2]:
        if token in _NAMED_COLORS:
            return _NAMED_COLORS[token]
    return None


def _resolve_vars(value: str, properties: Mapping[str, str], depth: int = 0) -> str:
    if depth > 5 or "var(" not in value:
        return value

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        fallback = match.group(2)
        if name in properties:
            return _resolve_vars(properties[name], properties, depth + 1)
        if fallback is not None:
            return _resolve_vars(fallback.strip(), properties, depth + 1)
        return match.group(0)

    return _VAR_RE.sub(_replace, value)


def _custom_properties(declarations: Sequence[Declaration]) -> dict[str, str]:
    properties: dict[str, str] = {}
    for declaration in declarations:
        if declaration.prop.startswith("--"):
            properties[declaration.prop] = declaration.value
    return properties


def _relative_luminance(color: tuple[int, int, int]) -> float:
    channels = []
    for value in color:
        channel = value / 255.0
        channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lighter = max(_relative_luminance(first), _relative_luminance(second))
    darker = min(_relative_luminance(first), _relative_luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


def _blocks(declarations: Sequence[Declaration]) -> dict[int, list[Declaration]]:
    result: dict[int, list[Declaration]] = {}
    for declaration in declarations:
        result.setdefault(declaration.block_id, []).append(declaration)
    return result


def _first(block: Sequence[Declaration], prop: str) -> Declaration | None:
    for declaration in block:
        if declaration.prop == prop:
            return declaration
    return None


# ---------------------------------------------------------------------------
# CSS/QSS rule checks
# ---------------------------------------------------------------------------
def _check_contrast(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    properties = _custom_properties(declarations)
    findings: list[dict[str, Any]] = []
    for block in _blocks(declarations).values():
        foreground = _first(block, "color")
        background = _first(block, "background-color") or _first(block, "background")
        if foreground is None or background is None:
            continue
        fg_color = _extract_color(_resolve_vars(foreground.value, properties))
        bg_color = _extract_color(_resolve_vars(background.value, properties))
        if fg_color is None or bg_color is None:
            continue
        ratio = _contrast_ratio(fg_color, bg_color)
        size = _font_size_px(block)
        weight = _font_weight(block)
        large = bool(size is not None and (size >= _LARGE_TEXT_PX or (size >= _LARGE_BOLD_TEXT_PX and weight >= 700)))
        threshold = _CONTRAST_LARGE if large else _CONTRAST_NORMAL
        if ratio + 1e-9 >= threshold:
            continue
        selector = foreground.selector or "<style>"
        findings.append(
            _finding(
                "UX-COLOR-001",
                file,
                foreground.line,
                f"text contrast {ratio:.2f}:1 is below {threshold:.1f}:1 for selector '{selector}'",
            )
        )
    return findings


_STATE_CUE_RE = re.compile(r"error|danger|invalid|warning|success|critical|failure|failed", re.I)
_COLOR_ONLY_PROPS = {
    "color",
    "background",
    "background-color",
    "border-color",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "outline-color",
    "text-decoration-color",
}


def _check_color_only(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for block in _blocks(declarations).values():
        selector = block[0].selector if block else ""
        if not _STATE_CUE_RE.search(selector):
            continue
        props = {declaration.prop for declaration in block}
        if not props & _COLOR_ONLY_PROPS or not props <= _COLOR_ONLY_PROPS:
            continue
        first = min(block, key=lambda declaration: (declaration.line, declaration.prop))
        findings.append(
            _finding(
                "UX-COLOR-002",
                file,
                first.line,
                f"state selector '{selector}' changes only color; add an icon, text, or shape cue",
            )
        )
    return findings


def _check_font_size(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop != "font-size":
            continue
        size = _length_px(declaration.value)
        if size is None or size + 1e-9 >= _MIN_FONT_SIZE_PX:
            continue
        findings.append(
            _finding(
                "UX-TYPE-001",
                file,
                declaration.line,
                f"font-size {_strip_important(declaration.value)!r} is below 12px for selector '{declaration.selector}'",
            )
        )
    return findings


def _ratio_from_line_height(value: str, font_size_px: float | None) -> float | None:
    raw = _strip_important(value).lower()
    match = _NUMBER_UNIT_RE.match(raw)
    if match:
        amount = float(match.group(1))
        unit = (match.group(2) or "").lower()
        if unit == "":
            return amount
        if unit == "em":
            return amount
        px = _length_px(raw)
        if px is None or font_size_px is None or font_size_px <= 0:
            return None
        return px / font_size_px
    percent = re.fullmatch(r"(-?\d*\.?\d+)\s*%", raw)
    if percent:
        return float(percent.group(1)) / 100.0
    return None


def _check_line_height(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for block in _blocks(declarations).values():
        size = _font_size_px(block)
        for declaration in block:
            if declaration.prop != "line-height":
                continue
            ratio = _ratio_from_line_height(declaration.value, size)
            if ratio is None or ratio + 1e-9 >= _MIN_LINE_HEIGHT:
                continue
            findings.append(
                _finding(
                    "UX-TYPE-002",
                    file,
                    declaration.line,
                    f"line-height ratio {ratio:.2f} is below 1.3 for selector '{declaration.selector}'",
                )
            )
    return findings


_SPACING_PROPS = {
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "gap",
    "row-gap",
    "column-gap",
}


def _check_spacing(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop not in _SPACING_PROPS:
            continue
        offending: str | None = None
        for token in _strip_important(declaration.value).split():
            lowered = token.lower()
            if "(" in lowered or lowered.endswith("%") or lowered in ("auto", "inherit", "initial", "unset", "normal"):
                continue
            px = _length_px(lowered)
            if px is None or px <= 0:
                continue
            if abs(px / _SPACING_GRID_PX - round(px / _SPACING_GRID_PX)) > 1e-6:
                offending = token
                break
        if offending is None:
            continue
        findings.append(
            _finding(
                "UX-SPACE-001",
                file,
                declaration.line,
                f"spacing value {offending!r} is outside the 4px token grid for selector '{declaration.selector}'",
            )
        )
    return findings


def _is_focus_selector(selector: str) -> bool:
    return "focus" in selector.lower()


def _is_visible_value(value: str) -> bool:
    lowered = _strip_important(value).lower()
    return lowered not in ("none", "0", "0px", "0 0", "initial", "unset", "transparent")


def _check_focus_visible(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    replacement_anywhere = False
    for declaration in declarations:
        if not _is_focus_selector(declaration.selector):
            continue
        if declaration.prop not in ("outline", "box-shadow", "border", "border-color", "border-width", "border-style"):
            continue
        if _is_visible_value(declaration.value):
            replacement_anywhere = True
            break
    findings: list[dict[str, Any]] = []
    seen_blocks: set[int] = set()
    for declaration in declarations:
        if declaration.prop != "outline" or declaration.block_id in seen_blocks:
            continue
        if _strip_important(declaration.value).lower() not in ("none", "0", "0px", "0 0", "initial"):
            continue
        seen_blocks.add(declaration.block_id)
        selector = declaration.selector
        if not (_is_focus_selector(selector) or selector.strip() in ("*", "a", "button", "input", "textarea", "select")):
            continue
        block = [item for item in declarations if item.block_id == declaration.block_id]
        replaced_here = any(
            item.prop in ("box-shadow", "border", "border-color", "border-width", "border-style")
            and _is_visible_value(item.value)
            for item in block
        )
        if replaced_here or replacement_anywhere:
            continue
        findings.append(
            _finding(
                "UX-A11Y-003",
                file,
                declaration.line,
                f"outline is removed for selector '{selector}' without a visible focus replacement",
            )
        )
    return findings


_MOTION_PROPS = {"animation", "animation-duration", "transition", "transition-duration", "transition-delay"}


def _animation_seconds(value: str) -> float | None:
    raw = _strip_important(value).lower()
    if raw in ("none", "initial", "unset", "0", "0s", "0ms"):
        return 0.0
    match = _ANIMATION_TIME_RE.search(raw)
    if not match:
        return None
    amount = float(match.group(1))
    return amount / 1000.0 if match.group(2).lower() == "s" else amount


def _is_reduced_motion_context(contexts: Sequence[str]) -> bool:
    for context in contexts:
        lowered = context.lower()
        if "prefers-reduced-motion" in lowered and "reduce" in lowered:
            return True
    return False


def _motion_disabled(value: str) -> bool:
    raw = _strip_important(value).lower()
    if raw in ("none", "initial", "unset", "0", "0s", "0ms", "0.01ms"):
        return True
    seconds = _animation_seconds(raw)
    return seconds is not None and seconds <= 0.001


def _check_motion(declarations: Sequence[Declaration], file: str) -> list[dict[str, Any]]:
    motion: list[Declaration] = []
    for declaration in declarations:
        if declaration.prop not in _MOTION_PROPS:
            continue
        seconds = _animation_seconds(declaration.value)
        if seconds is not None and seconds > 0.0:
            motion.append(declaration)
    if not motion:
        return []
    for declaration in declarations:
        if declaration.prop not in _MOTION_PROPS:
            continue
        if _is_reduced_motion_context(declaration.contexts) and _motion_disabled(declaration.value):
            return []
    first = min(motion, key=lambda declaration: (declaration.line, declaration.block_id))
    return [
        _finding(
            "UX-MOTION-001",
            file,
            first.line,
            "motion is declared without a prefers-reduced-motion: reduce guard",
        )
    ]


def _check_style_sheet(sheet: StyleSheet, file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    declarations = sheet.declarations
    findings.extend(_check_contrast(declarations, file))
    findings.extend(_check_color_only(declarations, file))
    findings.extend(_check_font_size(declarations, file))
    findings.extend(_check_line_height(declarations, file))
    findings.extend(_check_spacing(declarations, file))
    findings.extend(_check_focus_visible(declarations, file))
    findings.extend(_check_motion(declarations, file))
    return findings


# ---------------------------------------------------------------------------
# HTML parsing and markup checks
# ---------------------------------------------------------------------------
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_HEADING_RE = re.compile(r"h([1-6])")
_INTERACTIVE_TAGS = {"button", "a", "input", "select", "textarea"}
_INTERACTIVE_ROLES = {
    "button",
    "link",
    "checkbox",
    "radio",
    "switch",
    "tab",
    "menuitem",
    "combobox",
    "textbox",
    "searchbox",
    "slider",
    "spinbutton",
}


@dataclass
class HtmlElement:
    tag: str
    attrs: dict[str, str]
    line: int
    parent: "HtmlElement | None" = None
    text_parts: list[str] = field(default_factory=list)
    element_id: str = ""

    @property
    def text(self) -> str:
        return " ".join("".join(self.text_parts).split())


def _attrs_dict(attrs: Sequence[tuple[str, str | None]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in attrs:
        key = key.lower()
        if key in result:
            continue
        result[key] = "" if value is None else value
    return result


class _HtmlScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[HtmlElement] = []
        self.stack: list[HtmlElement] = []
        self.headings: list[tuple[int, int]] = []
        self.style_attrs: list[tuple[str, int, str]] = []
        self.style_blocks: list[tuple[str, int]] = []
        self.ids: dict[str, str] = {}
        self.labels: dict[str, str] = {}
        self._in_style = False
        self._in_script = False
        self._style_chunks: list[str] = []
        self._style_start_line = 1
        self._style_last_line = 1

    # -- helpers -----------------------------------------------------------
    def _append_ancestor_text(self, text: str) -> None:
        if not text:
            return
        for element in self.stack:
            element.text_parts.append(text)

    def _record_style_block(self) -> None:
        css = "".join(self._style_chunks).strip("\n")
        if css.strip():
            self.style_blocks.append((css, self._style_start_line))
        self._style_chunks = []

    # -- HTMLParser hooks --------------------------------------------------
    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        line = self.getpos()[0]
        values = _attrs_dict(attrs)
        if tag == "style":
            self._in_style = True
            self._style_chunks = []
            self._style_start_line = line
            self._style_last_line = line
            return
        if tag == "script":
            self._in_script = True
            return
        if values.get("aria-label"):
            self._append_ancestor_text(values["aria-label"])
        if tag == "img" and values.get("alt"):
            self._append_ancestor_text(values["alt"])
        element = HtmlElement(tag, values, line, self.stack[-1] if self.stack else None)
        if values.get("id"):
            element.element_id = values["id"]
            self.ids.setdefault(element.element_id, "")
        self.elements.append(element)
        heading = _HEADING_RE.fullmatch(tag)
        if heading:
            self.headings.append((int(heading.group(1)), line))
        if values.get("style", "").strip():
            self.style_attrs.append((values["style"], line, tag))
        if tag in _VOID_TAGS:
            return
        self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        line = self.getpos()[0]
        values = _attrs_dict(attrs)
        if values.get("aria-label"):
            self._append_ancestor_text(values["aria-label"])
        if tag == "img" and values.get("alt"):
            self._append_ancestor_text(values["alt"])
        element = HtmlElement(tag, values, line, self.stack[-1] if self.stack else None)
        if values.get("id"):
            element.element_id = values["id"]
            self.ids.setdefault(element.element_id, "")
        self.elements.append(element)
        heading = _HEADING_RE.fullmatch(tag)
        if heading:
            self.headings.append((int(heading.group(1)), line))
        if values.get("style", "").strip():
            self.style_attrs.append((values["style"], line, tag))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style":
            self._record_style_block()
            self._in_style = False
            return
        if tag == "script":
            self._in_script = False
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if self._in_style:
            line = self.getpos()[0]
            if self._style_chunks and line > self._style_last_line:
                self._style_chunks.append("\n" * (line - self._style_last_line))
            self._style_chunks.append(data)
            self._style_last_line = line + data.count("\n")
            return
        if self._in_script:
            return
        self._append_ancestor_text(data)

    def finalize(self) -> None:
        for element in self.elements:
            if element.element_id:
                self.ids[element.element_id] = element.text
            if element.tag == "label":
                target = element.attrs.get("for", "").strip()
                if target and element.text.strip():
                    self.labels.setdefault(target, element.text)


def _scan_html(text: str) -> _HtmlScan:
    scanner = _HtmlScan()
    scanner.feed(text)
    scanner.close()
    scanner.finalize()
    return scanner


def _is_interactive(element: HtmlElement) -> bool:
    return element.tag in _INTERACTIVE_TAGS or element.attrs.get("role", "").lower() in _INTERACTIVE_ROLES


def _input_type(element: HtmlElement) -> str:
    return element.attrs.get("type", "text").strip().lower() or "text"


def _accessible_name(element: HtmlElement, scan: _HtmlScan) -> str | None:
    attrs = element.attrs
    if attrs.get("aria-hidden", "").lower() == "true":
        return None
    for key in ("aria-label", "title"):
        if attrs.get(key, "").strip():
            return attrs[key].strip()
    labelled_by = attrs.get("aria-labelledby", "").strip()
    if labelled_by:
        names = [scan.ids.get(part.strip(), "") for part in labelled_by.split()]
        joined = " ".join(name for name in names if name).strip()
        if joined:
            return joined
        # An ID reference exists even if the target text is not statically
        # resolvable; do not raise a false hard FAIL for it.
        return labelled_by
    if element.tag == "input":
        input_type = _input_type(element)
        if input_type == "hidden":
            return None
        if input_type in ("submit", "button", "reset") and attrs.get("value", "").strip():
            return attrs["value"].strip()
        if input_type == "image" and attrs.get("alt", "").strip():
            return attrs["alt"].strip()
    label_text = scan.labels.get(element.element_id, "") if element.element_id else ""
    if label_text.strip():
        return label_text.strip()
    parent = element.parent
    while parent is not None:
        if parent.tag == "label" and parent.text.strip():
            return parent.text.strip()
        parent = parent.parent
    if element.text.strip():
        return element.text.strip()
    return None


def _check_accessible_names(scan: _HtmlScan, file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for element in scan.elements:
        if not _is_interactive(element):
            continue
        if element.tag == "input" and _input_type(element) == "hidden":
            continue
        if _accessible_name(element, scan) is not None:
            continue
        label = f"<{element.tag}>" + (f"#{element.element_id}" if element.element_id else "")
        findings.append(
            _finding(
                "UX-A11Y-001",
                file,
                element.line,
                f"interactive element {label} has no accessible name",
                evidence_ref=label,
            )
        )
    return findings


def _check_headings(scan: _HtmlScan, file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    previous: int | None = None
    for level, line in scan.headings:
        if previous is not None and level > previous + 1:
            findings.append(
                _finding(
                    "UX-A11Y-004",
                    file,
                    line,
                    f"heading level h{level} jumps from h{previous}",
                )
            )
        previous = level
    return findings


_ERROR_CLASS_RE = re.compile(r"error|danger|invalid|warning|fail(?:ed|ure)?|critical", re.I)
_ACTION_CUE_RE = re.compile(
    r"\b(?:retry|try again|re-?enter|check|verify|contact|support|enter|choose|select|update|"
    r"correct|fix|refresh|reload|learn more|review|edit|save again)\b"
    r"|重试|再试|请检查|检查|联系|修改|重新|选择|输入|更正|刷新|返回|重填|确认|了解|查看",
    re.I,
)


def _check_error_copy(scan: _HtmlScan, file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen_lines: set[int] = set()
    for element in scan.elements:
        if element.line in seen_lines:
            continue
        classes = element.attrs.get("class", "")
        role = element.attrs.get("role", "").lower()
        if role != "alert" and not _ERROR_CLASS_RE.search(classes):
            continue
        text = element.text
        if not text or _ACTION_CUE_RE.search(text):
            continue
        seen_lines.add(element.line)
        findings.append(
            _finding(
                "UX-COPY-001",
                file,
                element.line,
                f"error copy has no executable next step: {text[:80]!r}",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Inline style fragments (HTML style attributes / TSX style objects)
# ---------------------------------------------------------------------------
def _add_inline_style(sheet: StyleSheet, style_value: str, line: int, selector: str) -> None:
    block_id = sheet.new_block()
    for chunk in style_value.split(";"):
        if ":" not in chunk:
            continue
        prop, _, value = chunk.partition(":")
        prop = prop.strip().lower()
        value = value.strip()
        if prop and value:
            sheet.add(prop, value, line, selector, block_id)


_TSX_STYLE_RE = re.compile(r"style=\{\{(?P<body>.*?)\}\}", re.S)


def _camel_to_kebab(key: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", key.strip()).lower()


def _split_js_object(body: str) -> list[str]:
    parts: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    depth = 0
    for char in body:
        if quote is not None:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
            buffer.append(char)
        elif char in "([{":
            depth += 1
            buffer.append(char)
        elif char in ")]}":
            depth -= 1
            buffer.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(buffer))
            buffer = []
        else:
            buffer.append(char)
    parts.append("".join(buffer))
    return parts


_UNITLESS_JS_PROPS = {
    "line-height",
    "opacity",
    "z-index",
    "order",
    "flex",
    "flex-grow",
    "flex-shrink",
    "font-weight",
}


def _js_style_declarations(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for part in _split_js_object(body):
        if ":" not in part:
            continue
        key, _, raw_value = part.partition(":")
        prop = _camel_to_kebab(key.strip().strip("'\""))
        value = raw_value.strip()
        if not prop or not value:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"`":
            value = value[1:-1]
        elif re.fullmatch(r"-?\d*\.?\d+", value):
            value = value if prop in _UNITLESS_JS_PROPS else f"{value}px"
        elif "${" in value or "(" in value:
            continue
        out.append((prop, value))
    return out


def _tsx_style_blocks(text: str) -> list[tuple[int, list[tuple[str, str]]]]:
    blocks: list[tuple[int, list[tuple[str, str]]]] = []
    for match in _TSX_STYLE_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        blocks.append((line, _js_style_declarations(match.group("body"))))
    return blocks


# ---------------------------------------------------------------------------
# Per-source and aggregate linting
# ---------------------------------------------------------------------------
def _normalize_file(file: str) -> str:
    path = Path(file)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(SUITE_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return file.replace("\\", "/").removeprefix("./")


def infer_stack(file: str | Path) -> str:
    """Return the stack for a file path; QSS is Qt, everything else is Web."""
    suffix = Path(str(file)).suffix.lower()
    return "qt" if suffix == ".qss" else "web"


def _lint_source(file: str, text: str, stack: str) -> list[dict[str, Any]]:
    if stack not in SUPPORTED_STACKS:
        raise ValueError(f"unsupported stack {stack!r}; expected one of {SUPPORTED_STACKS}")
    suffix = Path(file).suffix.lower()
    sheet = StyleSheet()
    html: _HtmlScan | None = None
    findings: list[dict[str, Any]] = []
    if suffix in (".html", ".htm"):
        html = _scan_html(text)
        for css_text, start_line in html.style_blocks:
            sheet.merge(parse_css(css_text, line_offset=start_line - 1))
        for style_value, line, tag in html.style_attrs:
            _add_inline_style(sheet, style_value, line, f"<{tag}>")
    elif suffix in (".tsx", ".jsx"):
        for line, pairs in _tsx_style_blocks(text):
            block_id = sheet.new_block()
            for prop, value in pairs:
                sheet.add(prop, value, line, "<tsx style>", block_id)
    else:
        sheet = parse_css(text)
    findings.extend(_check_style_sheet(sheet, file))
    if html is not None:
        findings.extend(_check_accessible_names(html, file))
        findings.extend(_check_headings(html, file))
        findings.extend(_check_error_copy(html, file))
    return findings


def _dedupe(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for finding in findings:
        key = (
            finding["rule_id"],
            finding["file"],
            finding["line"],
            finding["message"],
            finding.get("evidence_ref"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


@lru_cache(maxsize=256)
def _scope_pattern(pattern: str) -> re.Pattern[str]:
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern[index : index + 2] == "**":
                if pattern[index + 2 : index + 3] == "/":
                    parts.append("(?:.*/)?")
                    index += 3
                    continue
                parts.append(".*")
                index += 2
                continue
            parts.append("[^/]*")
            index += 1
        elif char == "?":
            parts.append("[^/]")
            index += 1
        elif char in ".+()[]{}|^$\\":
            parts.append("\\" + char)
            index += 1
        else:
            parts.append(char)
            index += 1
    return re.compile("^" + "".join(parts) + "$")


def _scope_matches(file: str, scope: str) -> bool:
    normalized = scope.replace("\\", "/").strip().removeprefix("./")
    if not normalized:
        return False
    if normalized.endswith("/"):
        normalized += "**"
    file_normalized = file.replace("\\", "/").removeprefix("./")
    return _scope_pattern(normalized).fullmatch(file_normalized) is not None


def _audit_record(exemption: Mapping[str, Any], status: str) -> dict[str, Any]:
    return {
        "rule_id": exemption.get("rule_id") if isinstance(exemption.get("rule_id"), str) else None,
        "scope": exemption.get("scope") if isinstance(exemption.get("scope"), str) else None,
        "owner": exemption.get("owner") if isinstance(exemption.get("owner"), str) else None,
        "approved_by": exemption.get("approved_by") if isinstance(exemption.get("approved_by"), str) else None,
        "ticket": exemption.get("ticket") if isinstance(exemption.get("ticket"), str) else None,
        "expires_at": exemption.get("expires_at") if isinstance(exemption.get("expires_at"), str) else None,
        "status": status,
        "problems": [],
        "suppressed_count": 0,
        "suppressed": [],
    }


def _apply_exemptions(
    findings: Sequence[dict[str, Any]],
    exemptions: Iterable[Mapping[str, Any]] | None,
    now: datetime | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = list(findings)
    audit: list[dict[str, Any]] = []
    for raw in list(exemptions or []):
        if not isinstance(raw, Mapping):
            audit.append(
                {
                    "rule_id": None,
                    "scope": None,
                    "owner": None,
                    "approved_by": None,
                    "ticket": None,
                    "expires_at": None,
                    "status": "rejected",
                    "problems": ["exemption must be a JSON object"],
                    "suppressed_count": 0,
                    "suppressed": [],
                }
            )
            continue
        exemption = dict(raw)
        record = _audit_record(exemption, "rejected")
        problems: list[str]
        try:
            problems = rules.check_exemption(exemption, now)
        except Exception as exc:  # noqa: BLE001 - schema failures must be audited, not crash
            problems = [f"exemption validation failed: {exc}"]
        if not problems:
            try:
                severity = _rule_severity(str(exemption["rule_id"]))
            except (KeyError, ValueError) as exc:
                problems = [str(exc)]
            else:
                if severity != "WARNING":
                    problems = [f"{exemption['rule_id']} severity is {severity}; only WARNING findings are exemptible"]
        if problems:
            record["problems"] = problems
            audit.append(record)
            continue
        scope = str(exemption["scope"])
        matched = [
            finding
            for finding in remaining
            if finding["rule_id"] == exemption["rule_id"] and _scope_matches(finding["file"], scope)
        ]
        if not matched:
            record["status"] = "unused"
            audit.append(record)
            continue
        for finding in matched:
            remaining.remove(finding)
        record["status"] = "applied"
        record["suppressed_count"] = len(matched)
        record["suppressed"] = [
            {"file": finding["file"], "line": finding["line"], "rule_id": finding["rule_id"]}
            for finding in sorted(matched, key=lambda item: (item["file"], item["line"], item["rule_id"]))
        ]
        audit.append(record)
    return remaining, audit


def _summary(findings: Sequence[dict[str, Any]]) -> dict[str, int]:
    summary = {"fail": 0, "warning": 0, "info": 0}
    for finding in findings:
        key = str(finding["severity"]).lower()
        if key not in summary:
            raise ValueError(f"unexpected severity outside RuleSeverity: {finding['severity']!r}")
        summary[key] += 1
    return summary


def _lint_items(
    items: Sequence[tuple[str, str, str]],
    *,
    exemptions: Iterable[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files_checked: list[str] = []
    for file, text, stack in items:
        files_checked.append(file)
        findings.extend(_lint_source(file, text, stack))
    remaining, audit = _apply_exemptions(_dedupe(findings), exemptions, now)
    remaining.sort(
        key=lambda finding: (
            finding["file"],
            finding["line"],
            finding["rule_id"],
            finding["message"],
            finding.get("evidence_ref", ""),
        )
    )
    summary = _summary(remaining)
    return {
        "ok": summary["fail"] == 0,
        "findings": remaining,
        "summary": summary,
        "exemptions_applied": audit,
        "linter_version": LINTER_VERSION,
        "detector": DETECTOR,
        "catalog_version": _catalog_version(),
        "files_checked": files_checked,
    }


def lint_text(
    text: str,
    *,
    file: str = "<input>",
    stack: str | None = None,
    exemptions: Iterable[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Lint in-memory text and return the stable JSON-compatible result dict."""
    normalized = _normalize_file(file)
    resolved_stack = stack or infer_stack(normalized)
    return _lint_items([(normalized, text, resolved_stack)], exemptions=exemptions, now=now)


def lint_file(
    path: str | Path,
    *,
    root: str | Path | None = None,
    stack: str | None = None,
    exemptions: Iterable[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Lint one file; ``file`` in findings is relative to ``root`` when possible."""
    root_path = Path(root).resolve() if root is not None else SUITE_ROOT
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    try:
        display = target.resolve().relative_to(root_path).as_posix()
    except ValueError:
        display = target.as_posix()
    return _lint_items(
        [(display, text, stack or infer_stack(target))],
        exemptions=exemptions,
        now=now,
    )


def lint_files(
    paths: Iterable[str | Path],
    *,
    root: str | Path | None = None,
    stack: str | None = None,
    exemptions: Iterable[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Lint several files in one deterministic pass (exemptions applied once)."""
    root_path = Path(root).resolve() if root is not None else SUITE_ROOT
    items: list[tuple[str, str, str]] = []
    for raw in paths:
        target = Path(raw)
        text = target.read_text(encoding="utf-8")
        try:
            display = target.resolve().relative_to(root_path).as_posix()
        except ValueError:
            display = target.as_posix()
        items.append((display, text, stack or infer_stack(target)))
    return _lint_items(items, exemptions=exemptions, now=now)


def dump_result(result: Mapping[str, Any]) -> str:
    """Serialize a result dict with stable key ordering and UTF-8 content."""
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
