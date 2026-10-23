"""Design-system token loader and consistency linter (Stage 2 / T2.3+T2.4).

Single source of truth: ``knowledge/design-system/tokens.v1.0.json`` (validated
against ``contracts/design-tokens.v1.3.3.schema.json``) plus its freeze record
``tokens.v1.0.freeze.json``.

The linter is a static, deterministic screen for CSS/QSS/TSX source. It reports
values that deviate from the frozen token set:

* hardcoded colors outside ``colors.*``      -> ``dimension="color_token"`` (WARNING)
* spacing outside ``spacing.*``              -> catalog rule ``UX-SPACE-001``
* ``font-size`` outside typography tokens   -> ``UX-TYPE-001`` when below the
  catalog minimum, otherwise ``dimension="font_size_token"`` (WARNING)
* ``line-height`` outside typography tokens -> ``UX-TYPE-002`` when too tight,
  otherwise ``dimension="line_height_token"`` (WARNING)
* motion duration outside ``motion.*``      -> catalog rule ``UX-MOTION-001``

Rule IDs and their severities are read from the frozen catalog
(``knowledge/rules/catalog.v1.0.json``); this module never invents a rule ID.
Values that cannot be statically resolved (unknown units, unresolved ``var()``,
``calc()``/``clamp()``, gradients, translucent colors, relative font sizes) are
skipped instead of guessed: silence means "not statically proven", not "clean".
Results are regex / lightweight-parser screening, not an AST or rendered proof
(SPEC V1.3.3 section 7).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import contracts, rules
from .enums import SUITE_ROOT
from .style_linter import (
    Declaration,
    _ANIMATION_TIME_RE,
    _extract_color,
    _ratio_from_line_height,
    _resolve_vars,
    _strip_important,
    _tsx_style_blocks,
    parse_css,
)

TOKENS_DIR = SUITE_ROOT / "knowledge" / "design-system"
TOKENS_PATH = TOKENS_DIR / "tokens.v1.0.json"
FREEZE_PATH = TOKENS_DIR / "tokens.v1.0.freeze.json"

DETECTOR = "design_system_linter"
LINTER_VERSION = "1.0"

SUPPORTED_STACKS = ("web", "qt")
SUPPORTED_SUFFIXES = (".css", ".qss", ".tsx", ".jsx")

# Rule IDs this module may emit; severities always come from the frozen catalog.
SUPPORTED_RULE_IDS = ("UX-SPACE-001", "UX-TYPE-001", "UX-TYPE-002", "UX-MOTION-001")
# Findings that cannot be mapped onto a frozen rule use a stable dimension name.
DIMENSIONS = ("color_token", "font_size_token", "line_height_token")
DIMENSION_WARNING = "WARNING"
TOKEN_NAMESPACES = (
    "colors",
    "spacing",
    "typography.fontSize",
    "typography.lineHeight",
    "motion",
)

_MIN_FONT_SIZE_PX = 12.0
_MIN_LINE_HEIGHT = 1.3
_PX_TOLERANCE = 0.01
_MS_TOLERANCE = 0.5

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

_COLOR_PROPS = {
    "color",
    "background",
    "background-color",
    "border",
    "border-top",
    "border-right",
    "border-bottom",
    "border-left",
    "border-color",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "outline",
    "outline-color",
    "text-decoration-color",
    "box-shadow",
    "text-shadow",
    "column-rule",
    "column-rule-color",
    "fill",
    "stroke",
    "caret-color",
    "accent-color",
}

_MOTION_PROPS = {"animation", "animation-duration", "transition", "transition-duration"}
_SKIP_SPACING_VALUES = {"auto", "inherit", "initial", "unset", "normal", "none", "revert", "revert-layer"}

_NUMBER_VALUE_RE = re.compile(r"^(-?\d*\.?\d+)(px|rem|em)?$", re.I)
_VAR_REF_RE = re.compile(r"var\(\s*(--[A-Za-z0-9-]+)\s*\)")


class _AliasCycle(ValueError):
    """Raised when token aliases form a cycle."""

    def __init__(self, chain: tuple[str, ...]) -> None:
        super().__init__("alias cycle: " + " -> ".join(chain))
        self.chain = chain


# ---------------------------------------------------------------------------
# Token loading, schema validation and freeze record
# ---------------------------------------------------------------------------
def load_tokens(path: str | Path | None = None) -> dict[str, Any]:
    """Load the frozen design tokens (by default the committed token set)."""
    return contracts.load_json(path or TOKENS_PATH)


def token_schema_errors(tokens: Mapping[str, Any]) -> list[str]:
    """Return JSON Schema errors for a token document (empty means valid)."""
    return contracts.validation_errors("design-tokens", dict(tokens))


def canonical_digest(tokens: Mapping[str, Any] | None = None) -> str:
    """Canonical SHA-256 digest of the token document."""
    return contracts.sha256_json(dict(tokens) if tokens is not None else load_tokens())


def freeze_record(tokens: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Derive the freeze summary that the freeze file must match."""
    doc = dict(tokens) if tokens is not None else load_tokens()
    return {
        "token_set_version": doc["token_set_version"],
        "theme": doc["theme"],
        "counts": {name: len(doc.get(name, {})) for name in ("colors", "spacing", "typography", "radii", "motion")},
        "sha256": canonical_digest(doc),
    }


def verify_frozen(
    freeze_path: str | Path | None = None,
    tokens: Mapping[str, Any] | None = None,
) -> list[str]:
    """Compare the committed freeze record with the current token document."""
    path = Path(freeze_path) if freeze_path else FREEZE_PATH
    if not path.is_file():
        return [f"freeze record missing: {path}"]
    frozen = contracts.load_json(path)
    current = freeze_record(tokens)
    problems: list[str] = []
    for key in ("token_set_version", "theme", "counts", "sha256"):
        if frozen.get(key) != current[key]:
            problems.append(f"freeze mismatch: {key} expected {frozen.get(key)!r} got {current[key]!r}")
    for key in ("source", "license"):
        if not isinstance(frozen.get(key), str) or not frozen[key]:
            problems.append(f"freeze record missing {key}")
    return problems


# ---------------------------------------------------------------------------
# Token index, aliases and comparison scales
# ---------------------------------------------------------------------------
def _fmt_number(value: float) -> str:
    return f"{float(value):g}"


def _css_length_px(value: str) -> float | None:
    """Resolve a CSS length for scanning; px and rem only (16px root)."""
    match = _NUMBER_VALUE_RE.match(_strip_important(value).lower())
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    if unit == "px":
        return amount
    if unit == "rem":
        return amount * 16.0
    # ``em`` is contextual in CSS; treat it as unknown instead of guessing.
    return None


def _token_length_px(value: Any) -> float | None:
    """Resolve a token-side spacing value (number = px, px/rem/em accepted)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = _NUMBER_VALUE_RE.match(_strip_important(str(value)).lower())
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    if unit == "px":
        return amount
    if unit in ("rem", "em"):
        # Token file convention: 1rem/1em == 16px (documented in DESIGN_SYSTEM.md).
        return amount * 16.0
    return None


def _canonical_color(value: Any) -> str | None:
    rgb = _extract_color(str(value))
    if rgb is None:
        return None
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _token_var_map(tokens: Mapping[str, Any]) -> dict[str, str]:
    """Map CSS custom-property names to raw token values (aliases unresolved)."""
    mapping: dict[str, str] = {}
    for key, value in tokens.get("colors", {}).items():
        mapping[f"--{key}"] = str(value)
    for key, value in tokens.get("spacing", {}).items():
        px = _token_length_px(value)
        if px is not None:
            mapping[f"--{key}"] = f"{_fmt_number(px)}px"
    for style, spec in tokens.get("typography", {}).items():
        mapping[f"--font-size-{style}"] = f"{_fmt_number(spec['fontSize'])}px"
        mapping[f"--line-height-{style}"] = _fmt_number(spec["lineHeight"])
        if "fontWeight" in spec:
            mapping[f"--font-weight-{style}"] = str(spec["fontWeight"])
        if "fontFamily" in spec:
            mapping[f"--font-family-{style}"] = str(spec["fontFamily"])
    for key, value in tokens.get("radii", {}).items():
        mapping[f"--radius-{key}"] = f"{_fmt_number(value)}px"
    for key, spec in tokens.get("motion", {}).items():
        mapping[f"--motion-{key}"] = f"{_fmt_number(spec['duration_ms'])}ms"
        if "easing" in spec:
            mapping[f"--motion-{key}-easing"] = str(spec["easing"])
    return mapping


def _resolve_token_value(value: str, mapping: Mapping[str, str], stack: tuple[str, ...]) -> str:
    """Resolve ``var(--token)`` chains inside token values; unresolved refs stay."""
    if "var(" not in value:
        return value

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in stack:
            raise _AliasCycle(stack + (name,))
        if name not in mapping:
            return match.group(0)
        return _resolve_token_value(mapping[name], mapping, stack + (name,))

    return _VAR_REF_RE.sub(_replace, value)


def semantic_problems(tokens: Mapping[str, Any] | None = None) -> list[str]:
    """Schema + alias semantics for a token document (empty means valid)."""
    doc = dict(tokens) if tokens is not None else load_tokens()
    problems = token_schema_errors(doc)
    if problems:
        return problems
    mapping = _token_var_map(doc)
    for css_var, raw in sorted(mapping.items()):
        if "var(" not in raw:
            continue
        try:
            resolved = _resolve_token_value(raw, mapping, (css_var,))
        except _AliasCycle as exc:
            problems.append(f"{css_var}: alias cycle {' -> '.join(exc.chain)}")
            continue
        if "var(" in resolved:
            problems.append(f"{css_var}: unresolved token alias {resolved!r}")
    return problems


def token_index(tokens: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Flatten the token set into CSS-variable records (deterministic order)."""
    doc = dict(tokens) if tokens is not None else load_tokens()
    mapping = _token_var_map(doc)
    records: list[dict[str, Any]] = []

    def _add(token: str, group: str, css_var: str, raw: str, value: str) -> None:
        resolved = _resolve_token_value(raw, mapping, (css_var,))
        records.append(
            {
                "token": token,
                "group": group,
                "css_var": css_var,
                "raw": raw,
                "value": value,
                "alias": "var(" in raw,
                "resolved": "var(" not in resolved,
            }
        )

    for key, raw in doc.get("colors", {}).items():
        css_var = f"--{key}"
        resolved = _resolve_token_value(str(raw), mapping, (css_var,))
        canonical = _canonical_color(resolved) or resolved
        _add(key, "colors", css_var, str(raw), canonical)
    for key, raw in doc.get("spacing", {}).items():
        px = _token_length_px(raw)
        _add(key, "spacing", f"--{key}", str(raw), f"{_fmt_number(px)}px" if px is not None else str(raw))
    for style, spec in doc.get("typography", {}).items():
        _add(
            f"{style}.fontSize",
            "typography",
            f"--font-size-{style}",
            str(spec["fontSize"]),
            f"{_fmt_number(spec['fontSize'])}px",
        )
        _add(
            f"{style}.lineHeight",
            "typography",
            f"--line-height-{style}",
            str(spec["lineHeight"]),
            _fmt_number(spec["lineHeight"]),
        )
        if "fontWeight" in spec:
            _add(
                f"{style}.fontWeight",
                "typography",
                f"--font-weight-{style}",
                str(spec["fontWeight"]),
                str(spec["fontWeight"]),
            )
        if "fontFamily" in spec:
            _add(
                f"{style}.fontFamily",
                "typography",
                f"--font-family-{style}",
                str(spec["fontFamily"]),
                str(spec["fontFamily"]),
            )
    for key, value in doc.get("radii", {}).items():
        _add(key, "radii", f"--radius-{key}", str(value), f"{_fmt_number(value)}px")
    for key, spec in doc.get("motion", {}).items():
        _add(
            f"{key}.duration_ms",
            "motion",
            f"--motion-{key}",
            str(spec["duration_ms"]),
            f"{_fmt_number(spec['duration_ms'])}ms",
        )
        if "easing" in spec:
            _add(
                f"{key}.easing",
                "motion",
                f"--motion-{key}-easing",
                str(spec["easing"]),
                str(spec["easing"]),
            )
    records.sort(key=lambda record: (record["group"], record["token"]))
    return records


def token_scale(tokens: Mapping[str, Any] | None = None) -> dict[str, tuple[Any, ...]]:
    """Derive the comparable value sets used by the consistency checks."""
    doc = dict(tokens) if tokens is not None else load_tokens()
    mapping = _token_var_map(doc)
    colors: set[str] = set()
    for key, raw in doc.get("colors", {}).items():
        try:
            resolved = _resolve_token_value(str(raw), mapping, (f"--{key}",))
        except _AliasCycle:
            continue
        canonical = _canonical_color(resolved)
        if canonical is not None:
            colors.add(canonical)
    spacing = sorted(
        {px for px in (_token_length_px(value) for value in doc.get("spacing", {}).values()) if px is not None}
    )
    font_sizes = sorted({float(spec["fontSize"]) for spec in doc.get("typography", {}).values()})
    line_heights = sorted({float(spec["lineHeight"]) for spec in doc.get("typography", {}).values()})
    motion_ms = sorted({float(spec["duration_ms"]) for spec in doc.get("motion", {}).values()})
    return {
        "colors": tuple(sorted(colors)),
        "spacing_px": tuple(spacing),
        "font_size_px": tuple(font_sizes),
        "line_height": tuple(line_heights),
        "motion_ms": tuple(motion_ms),
    }


# ---------------------------------------------------------------------------
# Frozen catalog access (same contract as the T1.2 style linter)
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
    if severity not in ("FAIL", "WARNING", "INFO"):
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


def dimensions() -> list[str]:
    """Return the dimension names available to non-rule findings."""
    return list(DIMENSIONS)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
def _finding(
    *,
    file: str,
    line: int,
    prop: str,
    token: str,
    expected: str,
    actual: str,
    message: str,
    rule_id: str | None = None,
    dimension: str | None = None,
) -> dict[str, Any]:
    if (rule_id is None) == (dimension is None):
        raise ValueError("exactly one of rule_id/dimension must be provided")
    if token not in TOKEN_NAMESPACES:
        raise ValueError(f"unknown token namespace: {token!r}")
    if dimension is not None and dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension: {dimension!r}")
    finding: dict[str, Any] = {
        "file": file,
        "line": int(max(1, line)),
        "prop": prop,
        "token": token,
        "expected": expected,
        "actual": actual,
        "severity": _rule_severity(rule_id) if rule_id is not None else DIMENSION_WARNING,
        "message": message,
    }
    if rule_id is not None:
        finding["rule_id"] = rule_id
    else:
        finding["dimension"] = dimension
    return finding


def _expected_spacing(scale: Mapping[str, Sequence[Any]]) -> str:
    values = ", ".join(f"{_fmt_number(value)}px" for value in scale["spacing_px"])
    return f"spacing token ({values})"


def _expected_font_size(scale: Mapping[str, Sequence[Any]]) -> str:
    values = ", ".join(f"{_fmt_number(value)}px" for value in scale["font_size_px"])
    return f"typography fontSize token ({values})"


def _expected_line_height(scale: Mapping[str, Sequence[Any]]) -> str:
    values = ", ".join(_fmt_number(value) for value in scale["line_height"])
    return f"typography lineHeight token ({values})"


def _expected_motion(scale: Mapping[str, Sequence[Any]]) -> str:
    values = ", ".join(f"{_fmt_number(value)}ms" for value in scale["motion_ms"])
    return f"motion duration token ({values})"


def _expected_color(scale: Mapping[str, Sequence[Any]]) -> str:
    return f"design-token color (colors.*, {len(scale['colors'])} resolved values)"


def _in_values(value: float, candidates: Sequence[float], tolerance: float) -> bool:
    return any(abs(value - candidate) <= tolerance for candidate in candidates)


# ---------------------------------------------------------------------------
# Source scanning
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
    return "qt" if Path(str(file)).suffix.lower() == ".qss" else "web"


def _parse_source(file: str, text: str) -> tuple[list[Declaration], dict[str, str]]:
    suffix = Path(file).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported source suffix {suffix!r}; expected one of {SUPPORTED_SUFFIXES}")
    declarations: list[Declaration] = []
    if suffix in (".tsx", ".jsx"):
        for block_id, (line, pairs) in enumerate(_tsx_style_blocks(text), start=1):
            for prop, value in pairs:
                declarations.append(Declaration(prop, value, line, "<tsx style>", block_id))
    else:
        declarations = parse_css(text).declarations
    local_vars = {declaration.prop: declaration.value for declaration in declarations if declaration.prop.startswith("--")}
    return declarations, local_vars


def _resolve_value(value: str, properties: Mapping[str, str]) -> str | None:
    """Resolve var() references; return ``None`` when anything stays unknown."""
    resolved = _resolve_vars(_strip_important(value), properties)
    if "var(" in resolved:
        return None
    return resolved


def _block_font_size(block: Sequence[Declaration], properties: Mapping[str, str]) -> float | None:
    for declaration in block:
        if declaration.prop != "font-size":
            continue
        resolved = _resolve_value(declaration.value, properties)
        if resolved is None:
            continue
        px = _css_length_px(resolved)
        if px is not None:
            return px
    return None


def _blocks(declarations: Sequence[Declaration]) -> dict[int, list[Declaration]]:
    result: dict[int, list[Declaration]] = {}
    for declaration in declarations:
        result.setdefault(declaration.block_id, []).append(declaration)
    return result


def _check_colors(
    declarations: Sequence[Declaration],
    properties: Mapping[str, str],
    scale: Mapping[str, Sequence[Any]],
    file: str,
) -> list[dict[str, Any]]:
    allowed = set(scale["colors"])
    expected = _expected_color(scale)
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop not in _COLOR_PROPS:
            continue
        resolved = _resolve_value(declaration.value, properties)
        if resolved is None:
            continue
        canonical = _canonical_color(resolved)
        if canonical is None or canonical in allowed:
            continue
        findings.append(
            _finding(
                file=file,
                line=declaration.line,
                prop=declaration.prop,
                token="colors",
                expected=expected,
                actual=canonical,
                dimension="color_token",
                message=(
                    f"hardcoded color {canonical!r} in '{declaration.prop}' is not a design-token color"
                ),
            )
        )
    return findings


def _check_spacing(
    declarations: Sequence[Declaration],
    properties: Mapping[str, str],
    scale: Mapping[str, Sequence[Any]],
    file: str,
) -> list[dict[str, Any]]:
    expected = _expected_spacing(scale)
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop not in _SPACING_PROPS:
            continue
        resolved = _resolve_value(declaration.value, properties)
        if resolved is None:
            continue
        lowered = resolved.lower()
        # calc()/clamp()/min()/max() and percentages are not statically comparable.
        if any(marker in lowered for marker in ("(", "%")):
            continue
        offending: str | None = None
        for token in resolved.split():
            candidate = token.lower()
            if candidate in _SKIP_SPACING_VALUES:
                continue
            px = _css_length_px(candidate)
            if px is None:
                continue
            if px <= 0:
                # 0 is a legal token value; negative values are optical adjustments.
                continue
            if not _in_values(px, scale["spacing_px"], _PX_TOLERANCE):
                offending = token
                break
        if offending is None:
            continue
        findings.append(
            _finding(
                file=file,
                line=declaration.line,
                prop=declaration.prop,
                token="spacing",
                expected=expected,
                actual=offending,
                rule_id="UX-SPACE-001",
                message=(
                    f"spacing value {offending!r} is outside the design-token spacing scale "
                    f"for '{declaration.prop}'"
                ),
            )
        )
    return findings


def _check_font_size(
    declarations: Sequence[Declaration],
    properties: Mapping[str, str],
    scale: Mapping[str, Sequence[Any]],
    file: str,
) -> list[dict[str, Any]]:
    expected = _expected_font_size(scale)
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop != "font-size":
            continue
        resolved = _resolve_value(declaration.value, properties)
        if resolved is None:
            continue
        px = _css_length_px(resolved)
        if px is None or px <= 0:
            continue
        if _in_values(px, scale["font_size_px"], _PX_TOLERANCE):
            continue
        actual = resolved
        if px + 1e-9 < _MIN_FONT_SIZE_PX:
            findings.append(
                _finding(
                    file=file,
                    line=declaration.line,
                    prop=declaration.prop,
                    token="typography.fontSize",
                    expected=expected,
                    actual=actual,
                    rule_id="UX-TYPE-001",
                    message=f"font-size {actual!r} is below 12px and outside the typography tokens",
                )
            )
        else:
            findings.append(
                _finding(
                    file=file,
                    line=declaration.line,
                    prop=declaration.prop,
                    token="typography.fontSize",
                    expected=expected,
                    actual=actual,
                    dimension="font_size_token",
                    message=f"font-size {actual!r} is not a typography fontSize token",
                )
            )
    return findings


def _check_line_height(
    declarations: Sequence[Declaration],
    properties: Mapping[str, str],
    scale: Mapping[str, Sequence[Any]],
    file: str,
) -> list[dict[str, Any]]:
    expected = _expected_line_height(scale)
    blocks = _blocks(declarations)
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop != "line-height":
            continue
        resolved = _resolve_value(declaration.value, properties)
        if resolved is None:
            continue
        font_size = _block_font_size(blocks.get(declaration.block_id, ()), properties)
        ratio = _ratio_from_line_height(resolved, font_size)
        if ratio is None or ratio <= 0:
            continue
        if _in_values(ratio, scale["line_height"], _PX_TOLERANCE):
            continue
        actual = resolved
        if ratio + 1e-9 < _MIN_LINE_HEIGHT:
            findings.append(
                _finding(
                    file=file,
                    line=declaration.line,
                    prop=declaration.prop,
                    token="typography.lineHeight",
                    expected=expected,
                    actual=actual,
                    rule_id="UX-TYPE-002",
                    message=f"line-height ratio {ratio:.2f} is below 1.3 and outside the typography tokens",
                )
            )
        else:
            findings.append(
                _finding(
                    file=file,
                    line=declaration.line,
                    prop=declaration.prop,
                    token="typography.lineHeight",
                    expected=expected,
                    actual=actual,
                    dimension="line_height_token",
                    message=f"line-height {actual!r} (ratio {ratio:.2f}) is not a typography lineHeight token",
                )
            )
    return findings


def _check_motion(
    declarations: Sequence[Declaration],
    properties: Mapping[str, str],
    scale: Mapping[str, Sequence[Any]],
    file: str,
) -> list[dict[str, Any]]:
    expected = _expected_motion(scale)
    findings: list[dict[str, Any]] = []
    for declaration in declarations:
        if declaration.prop not in _MOTION_PROPS:
            continue
        resolved = _resolve_value(declaration.value, properties)
        if resolved is None:
            continue
        match = _ANIMATION_TIME_RE.search(resolved.lower())
        if match is None:
            continue
        amount = float(match.group(1))
        offending = amount * 1000.0 if match.group(2).lower() == "s" else amount
        if offending <= 0 or _in_values(offending, scale["motion_ms"], _MS_TOLERANCE):
            continue
        actual = resolved
        findings.append(
            _finding(
                file=file,
                line=declaration.line,
                prop=declaration.prop,
                token="motion",
                expected=expected,
                actual=actual,
                rule_id="UX-MOTION-001",
                message=(
                    f"motion duration {_fmt_number(offending)}ms is outside the design-token motion scale; "
                    "reduced-motion behavior is unverified"
                ),
            )
        )
    return findings


def _scan(
    file: str,
    text: str,
    stack: str,
    properties_base: Mapping[str, str],
    scale: Mapping[str, Sequence[Any]],
) -> list[dict[str, Any]]:
    if stack not in SUPPORTED_STACKS:
        raise ValueError(f"unsupported stack {stack!r}; expected one of {SUPPORTED_STACKS}")
    declarations, local_vars = _parse_source(file, text)
    properties = dict(properties_base)
    properties.update(local_vars)
    findings: list[dict[str, Any]] = []
    findings.extend(_check_colors(declarations, properties, scale, file))
    findings.extend(_check_spacing(declarations, properties, scale, file))
    findings.extend(_check_font_size(declarations, properties, scale, file))
    findings.extend(_check_line_height(declarations, properties, scale, file))
    findings.extend(_check_motion(declarations, properties, scale, file))
    return findings


# ---------------------------------------------------------------------------
# Aggregate result
# ---------------------------------------------------------------------------
def _finding_id(finding: Mapping[str, Any]) -> str:
    return str(finding.get("rule_id") or finding.get("dimension"))


def _dedupe(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for finding in findings:
        key = (
            finding["file"],
            finding["line"],
            _finding_id(finding),
            finding["prop"],
            finding["actual"],
            finding["message"],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(finding)
    return out


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
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    doc = dict(tokens) if tokens is not None else load_tokens()
    problems = semantic_problems(doc)
    if problems:
        raise ValueError(f"invalid design tokens: {problems[0]}")
    findings: list[dict[str, Any]] = []
    files_checked: list[str] = []
    properties_base = _token_var_map(doc)
    scale = token_scale(doc)
    for file, text, stack in items:
        files_checked.append(file)
        findings.extend(_scan(file, text, stack, properties_base, scale))
    remaining = _dedupe(findings)
    remaining.sort(
        key=lambda finding: (
            finding["file"],
            finding["line"],
            _finding_id(finding),
            finding["prop"],
            finding["actual"],
            finding["message"],
        )
    )
    summary = _summary(remaining)
    return {
        "ok": not remaining,
        "findings": remaining,
        "summary": summary,
        "detector": DETECTOR,
        "linter_version": LINTER_VERSION,
        "token_set_version": doc["token_set_version"],
        "token_sha256": canonical_digest(doc),
        "dimensions": list(DIMENSIONS),
        "catalog_version": _catalog_version(),
        "files_checked": files_checked,
    }


def lint_text(
    text: str,
    *,
    file: str = "input.css",
    stack: str | None = None,
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lint in-memory CSS/QSS/TSX text and return the stable JSON-compatible result."""
    normalized = _normalize_file(file)
    resolved_stack = stack or infer_stack(normalized)
    return _lint_items([(normalized, text, resolved_stack)], tokens=tokens)


def lint_file(
    path: str | Path,
    *,
    root: str | Path | None = None,
    stack: str | None = None,
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lint one file; ``file`` in findings is relative to ``root`` when possible."""
    root_path = Path(root).resolve() if root is not None else SUITE_ROOT
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    try:
        display = target.resolve().relative_to(root_path).as_posix()
    except ValueError:
        display = target.as_posix()
    return _lint_items([(display, text, stack or infer_stack(target))], tokens=tokens)


def lint_files(
    paths: Iterable[str | Path],
    *,
    root: str | Path | None = None,
    stack: str | None = None,
    tokens: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lint several files in one deterministic pass."""
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
    return _lint_items(items, tokens=tokens)


def dump_result(result: Mapping[str, Any]) -> str:
    """Serialize a result dict with stable key ordering and UTF-8 content."""
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
