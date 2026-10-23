"""Layout geometry probe in measurement-JSON mode (Stage 1 / T1.4).

Stage 1 consumes *measurement documents* produced by an external measurement
step (browser DOM metrics, Qt offscreen metrics, design-tool export). Stage 3
owns the live-GUI / native probe. Every report from this module is therefore
``SIMULATED`` and must never be presented as ``NATIVE_APP`` evidence.

Only frozen rule IDs from ``knowledge/rules/catalog.v1.0.json`` are emitted:

  UX-SPACE-002  interactive target smaller than 24x24 CSS px
  UX-GEOM-001   text / key control clipped, overflowing or invisible
  UX-GEOM-002   two interactive targets overlap
  UX-COLOR-001  text contrast below WCAG 2.2 AA
  UX-A11Y-003   keyboard focus has no visible indicator (or < 3:1 ring)
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple, Sequence

from .rules import load_catalog

PROBE_ID = "layout_geometry_probe"
PROBE_MODE = "measurement_json"
RUNTIME_LEVEL = "SIMULATED"

RULE_TARGET_SIZE = "UX-SPACE-002"
RULE_CLIPPING = "UX-GEOM-001"
RULE_OVERLAP = "UX-GEOM-002"
RULE_CONTRAST = "UX-COLOR-001"
RULE_FOCUS = "UX-A11Y-003"

SUPPORTED_RULES: tuple[str, ...] = (
    RULE_TARGET_SIZE,
    RULE_CLIPPING,
    RULE_OVERLAP,
    RULE_CONTRAST,
    RULE_FOCUS,
)

#: Rules this probe must own in the catalog (fail closed on catalog drift).
PROBE_OWNED_RULES: tuple[str, ...] = (RULE_TARGET_SIZE, RULE_CLIPPING, RULE_OVERLAP)

TARGET_MIN_PX = 24.0
CONTRAST_NORMAL_MIN = 4.5
CONTRAST_LARGE_MIN = 3.0
FOCUS_CONTRAST_MIN = 3.0
LARGE_TEXT_PX = 24.0
LARGE_BOLD_TEXT_PX = 18.66
BOLD_FONT_WEIGHT = 700
DEFAULT_FONT_WEIGHT = 400
DEFAULT_CANVAS_COLOR = "#ffffff"

#: Sub-pixel tolerance used for containment / overlap / text-fit decisions.
GEOMETRY_TOLERANCE_PX = 0.5

_STYLE_KEYS = frozenset(
    {"fontSize", "lineHeight", "color", "bgColor", "focusVisible", "focusColor", "fontWeight"}
)
_OVERFLOW_FLAG_KEYS = frozenset({"hidden", "clipped", "scrollable", "ellipsis"})
_OVERFLOW_SIZE_KEYS = frozenset({"scrollWidth", "clientWidth", "scrollHeight", "clientHeight"})
_OVERFLOW_KEYS = _OVERFLOW_FLAG_KEYS | _OVERFLOW_SIZE_KEYS

_HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB_COLOR_RE = re.compile(r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$")

RGB = tuple[int, int, int]


class MeasurementError(ValueError):
    """Raised when a measurement document violates the T1.4 contract."""


class Rect(NamedTuple):
    """Border-box rectangle in CSS px, origin at the viewport top-left."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h


# ---------------------------------------------------------------------------
# Colors and WCAG 2.2 contrast
# ---------------------------------------------------------------------------


def parse_color(value: str) -> RGB:
    """Parse ``#rgb``, ``#rrggbb`` or ``rgb(r, g, b)`` into an RGB tuple."""
    if not isinstance(value, str):
        raise MeasurementError(f"color must be a string, got {value!r}")
    text = value.strip()
    hex_match = _HEX_COLOR_RE.match(text)
    if hex_match:
        digits = hex_match.group(1)
        if len(digits) == 3:
            digits = "".join(char * 2 for char in digits)
        return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
    rgb_match = _RGB_COLOR_RE.match(text)
    if rgb_match:
        channels = tuple(int(part) for part in rgb_match.groups())
        if any(channel > 255 for channel in channels):
            raise MeasurementError(f"rgb() channel out of range 0-255: {text!r}")
        return (channels[0], channels[1], channels[2])
    raise MeasurementError(
        f"unsupported color {text!r}; expected #rgb, #rrggbb or rgb(r, g, b)"
    )


def _as_rgb(color: str | Sequence[int]) -> RGB:
    if isinstance(color, str):
        return parse_color(color)
    if isinstance(color, (tuple, list)) and len(color) == 3:
        channels: list[int] = []
        for channel in color:
            if isinstance(channel, bool) or not isinstance(channel, int):
                raise MeasurementError(f"rgb channels must be integers, got {color!r}")
            if not 0 <= channel <= 255:
                raise MeasurementError(f"rgb channel out of range 0-255: {color!r}")
            channels.append(channel)
        return (channels[0], channels[1], channels[2])
    raise MeasurementError(f"invalid color value {color!r}")


def _channel_luminance(channel: int) -> float:
    value = channel / 255.0
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _luminance(rgb: RGB) -> float:
    red, green, blue = (_channel_luminance(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def relative_luminance(color: str | Sequence[int]) -> float:
    """WCAG 2.2 relative luminance of a color (0.0 = black, 1.0 = white)."""
    return _luminance(_as_rgb(color))


def contrast_ratio(foreground: str | Sequence[int], background: str | Sequence[int]) -> float:
    """WCAG 2.2 contrast ratio between two opaque colors (1.0 .. 21.0)."""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def is_large_text(font_size: float, font_weight: float = DEFAULT_FONT_WEIGHT) -> bool:
    """WCAG 2.2 large text: >= 24 px, or >= 18.66 px when bold."""
    if font_size >= LARGE_TEXT_PX:
        return True
    return font_weight >= BOLD_FONT_WEIGHT and font_size >= LARGE_BOLD_TEXT_PX


# ---------------------------------------------------------------------------
# Catalog guard
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def catalog_severities() -> dict[str, str]:
    """Severity per frozen rule ID; raises if the catalog lost a supported rule."""
    table = {rule["rule_id"]: rule["severity"] for rule in load_catalog()["rules"]}
    missing = [rule_id for rule_id in SUPPORTED_RULES if rule_id not in table]
    if missing:
        raise RuntimeError(f"frozen catalog is missing probe rules: {', '.join(missing)}")
    return table


@lru_cache(maxsize=1)
def _verify_probe_ownership() -> None:
    catalog = load_catalog()
    detectors = {rule["rule_id"]: rule["detector"] for rule in catalog["rules"]}
    wrong = [
        f"{rule_id} (detector={detectors.get(rule_id)!r})"
        for rule_id in PROBE_OWNED_RULES
        if detectors.get(rule_id) != PROBE_ID
    ]
    if wrong:
        raise RuntimeError(f"catalog detector drift for geometry rules: {', '.join(wrong)}")


# ---------------------------------------------------------------------------
# Measurement normalization
# ---------------------------------------------------------------------------


class Element(NamedTuple):
    """Normalized measurement element."""

    id: str
    role: str
    rect: Rect
    text: str
    styles: dict[str, Any]
    interactive: bool
    overflow: dict[str, Any]
    parent_id: str | None


class Measurement(NamedTuple):
    viewport: dict[str, float]
    canvas: RGB
    elements: tuple[Element, ...]
    by_id: dict[str, Element]


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: Any, where: str) -> float:
    if not _is_finite_number(value):
        raise MeasurementError(f"{where} must be a finite number, got {value!r}")
    return float(value)


def _non_negative(value: Any, where: str) -> float:
    result = _number(value, where)
    if result < 0:
        raise MeasurementError(f"{where} must be >= 0, got {result!r}")
    return result


def _boolean(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise MeasurementError(f"{where} must be a boolean, got {value!r}")
    return value


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MeasurementError(f"{where} must be an object, got {type(value).__name__}")
    return value


def _rect(raw: Any, where: str) -> Rect:
    data = _object(raw, where)
    for key in ("x", "y", "w", "h"):
        if key not in data:
            raise MeasurementError(f"{where} is missing required key {key!r}")
    return Rect(
        x=_number(data["x"], f"{where}.x"),
        y=_number(data["y"], f"{where}.y"),
        w=_non_negative(data["w"], f"{where}.w"),
        h=_non_negative(data["h"], f"{where}.h"),
    )


def _styles(raw: Any, element_id: str) -> dict[str, Any]:
    if raw is None:
        return {}
    data = _object(raw, f"element {element_id!r}.styles")
    unknown = sorted(set(data) - _STYLE_KEYS)
    if unknown:
        raise MeasurementError(
            f"element {element_id!r}.styles has unknown keys: {', '.join(unknown)}"
        )
    styles: dict[str, Any] = {}
    for key in ("fontSize", "lineHeight"):
        if key in data:
            value = _number(data[key], f"element {element_id!r}.styles.{key}")
            if value <= 0:
                raise MeasurementError(
                    f"element {element_id!r}.styles.{key} must be > 0, got {value!r} (CSS px)"
                )
            styles[key] = value
    if "fontWeight" in data:
        weight = _number(data["fontWeight"], f"element {element_id!r}.styles.fontWeight")
        if not 1 <= weight <= 1000:
            raise MeasurementError(
                f"element {element_id!r}.styles.fontWeight must be within 1..1000"
            )
        styles["fontWeight"] = weight
    for key in ("color", "bgColor", "focusColor"):
        if key in data:
            # parse_color raises MeasurementError with the offending value
            styles[key] = parse_color(data[key])
    if "focusVisible" in data:
        styles["focusVisible"] = _boolean(
            data["focusVisible"], f"element {element_id!r}.styles.focusVisible"
        )
    return styles


def _overflow(raw: Any, element_id: str) -> dict[str, Any]:
    if raw is None:
        return {}
    data = _object(raw, f"element {element_id!r}.overflow")
    unknown = sorted(set(data) - _OVERFLOW_KEYS)
    if unknown:
        raise MeasurementError(
            f"element {element_id!r}.overflow has unknown keys: {', '.join(unknown)}"
        )
    overflow: dict[str, Any] = {}
    for key in _OVERFLOW_SIZE_KEYS:
        if key in data:
            overflow[key] = _non_negative(data[key], f"element {element_id!r}.overflow.{key}")
    for key in _OVERFLOW_FLAG_KEYS:
        if key in data:
            overflow[key] = _boolean(data[key], f"element {element_id!r}.overflow.{key}")
    return overflow


def _optional_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MeasurementError(f"{where} must be a non-empty string, got {value!r}")
    return value


def _text(raw: Any, element_id: str) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise MeasurementError(f"element {element_id!r}.text must be a string")
    return raw


def normalize_measurement(measurement: Any) -> Measurement:
    """Validate a measurement document and return its normalized form."""
    data = _object(measurement, "measurement")
    if "viewport" not in data:
        raise MeasurementError("measurement is missing required key 'viewport'")
    viewport = _object(data["viewport"], "measurement.viewport")
    if "w" not in viewport or "h" not in viewport:
        raise MeasurementError("measurement.viewport must contain 'w' and 'h'")
    normalized_viewport = {
        "w": _number(viewport["w"], "measurement.viewport.w"),
        "h": _number(viewport["h"], "measurement.viewport.h"),
    }
    if normalized_viewport["w"] <= 0 or normalized_viewport["h"] <= 0:
        raise MeasurementError("measurement.viewport.w/h must be > 0")
    if "background" in data and data["background"] is not None:
        canvas = parse_color(data["background"])
    else:
        canvas = parse_color(DEFAULT_CANVAS_COLOR)
    if "elements" not in data:
        raise MeasurementError("measurement is missing required key 'elements'")
    raw_elements = data["elements"]
    if not isinstance(raw_elements, list):
        raise MeasurementError("measurement.elements must be a list")

    elements: list[Element] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_elements):
        where = f"measurement.elements[{index}]"
        item = _object(raw, where)
        element_id = _optional_string(item.get("id"), f"{where}.id")
        if element_id is None:
            raise MeasurementError(f"{where}.id must be a non-empty string")
        if element_id in seen:
            raise MeasurementError(f"duplicate element id: {element_id!r}")
        seen.add(element_id)
        role = _optional_string(item.get("role"), f"element {element_id!r}.role")
        if role is None:
            raise MeasurementError(f"element {element_id!r}.role must be a non-empty string")
        if "rect" not in item:
            raise MeasurementError(f"element {element_id!r} is missing required key 'rect'")
        interactive = False
        if "interactive" in item:
            interactive = _boolean(item["interactive"], f"element {element_id!r}.interactive")
        elements.append(
            Element(
                id=element_id,
                role=role,
                rect=_rect(item["rect"], f"element {element_id!r}.rect"),
                text=_text(item.get("text"), element_id),
                styles=_styles(item.get("styles"), element_id),
                interactive=interactive,
                overflow=_overflow(item.get("overflow"), element_id),
                parent_id=_optional_string(
                    item.get("parentId"), f"element {element_id!r}.parentId"
                ),
            )
        )

    by_id = {element.id: element for element in elements}
    for element in elements:
        if element.parent_id is not None:
            if element.parent_id == element.id:
                raise MeasurementError(f"element {element.id!r} cannot be its own parent")
            if element.parent_id not in by_id:
                raise MeasurementError(
                    f"element {element.id!r}.parentId references unknown element "
                    f"{element.parent_id!r}"
                )
    _check_parent_cycles(elements)
    return Measurement(
        viewport=normalized_viewport,
        canvas=canvas,
        elements=tuple(elements),
        by_id=by_id,
    )


def _check_parent_cycles(elements: Sequence[Element]) -> None:
    by_id = {element.id: element for element in elements}
    for element in elements:
        path: list[str] = []
        current: Element | None = element
        while current is not None:
            if current.id in path:
                cycle = " -> ".join([*path[path.index(current.id):], current.id])
                raise MeasurementError(f"parentId cycle detected: {cycle}")
            path.append(current.id)
            current = by_id[current.parent_id] if current.parent_id else None


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _intersection(first: Rect, second: Rect) -> Rect | None:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)
    if right <= left or bottom <= top:
        return None
    return Rect(left, top, right - left, bottom - top)


def _contains(outer: Rect, inner: Rect, tolerance: float = GEOMETRY_TOLERANCE_PX) -> bool:
    return (
        inner.x >= outer.x - tolerance
        and inner.y >= outer.y - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def _effective_background(element: Element, measurement: Measurement) -> RGB:
    """Background of the element's own box (nearest own/ancestor bgColor)."""
    current: Element | None = element
    while current is not None:
        color = current.styles.get("bgColor")
        if color is not None:
            return color
        current = measurement.by_id[current.parent_id] if current.parent_id else None
    return measurement.canvas


def _ancestor_background(element: Element, measurement: Measurement) -> RGB:
    """Background behind the element's box (focus rings are painted outside it)."""
    if element.parent_id is None:
        return measurement.canvas
    parent = measurement.by_id[element.parent_id]
    return _effective_background(parent, measurement)


def _is_content(element: Element) -> bool:
    """Text-bearing or interactive elements are the clipping rule's targets."""
    return bool(element.text) or element.interactive


def _fmt(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _rect_payload(rect: Rect) -> dict[str, float]:
    return {"x": rect.x, "y": rect.y, "w": rect.w, "h": rect.h}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _finding(
    rule_id: str,
    element_id: str,
    message: str,
    *,
    related_element_id: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "rule_id": rule_id,
        "severity": catalog_severities()[rule_id],
        "element_id": element_id,
        "message": message,
    }
    if related_element_id is not None:
        finding["related_element_id"] = related_element_id
    if evidence:
        finding["evidence"] = evidence
    return finding


def _check_target_size(measurement: Measurement) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for element in measurement.elements:
        if not element.interactive:
            continue
        rect = element.rect
        if rect.w < TARGET_MIN_PX or rect.h < TARGET_MIN_PX:
            findings.append(
                _finding(
                    RULE_TARGET_SIZE,
                    element.id,
                    (
                        f"interactive target measures {_fmt(rect.w)}x{_fmt(rect.h)} CSS px; "
                        f"WCAG 2.2 AA requires at least {_fmt(TARGET_MIN_PX)}x{_fmt(TARGET_MIN_PX)}"
                    ),
                    evidence={
                        "role": element.role,
                        "rect": _rect_payload(rect),
                        "threshold_px": TARGET_MIN_PX,
                    },
                )
            )
    return findings


def _clipping_reasons(element: Element, measurement: Measurement) -> list[str]:
    if not _is_content(element):
        return []
    reasons: list[str] = []
    rect = element.rect
    overflow = element.overflow

    if overflow.get("clipped"):
        reasons.append("measurement reports the element as clipped")
    if not overflow.get("scrollable"):
        scroll_width = overflow.get("scrollWidth")
        client_width = overflow.get("clientWidth")
        if scroll_width is not None and client_width is not None:
            if scroll_width - client_width > GEOMETRY_TOLERANCE_PX and not overflow.get("ellipsis"):
                reasons.append(
                    f"content width {_fmt(scroll_width)} exceeds box width {_fmt(client_width)}"
                )
        scroll_height = overflow.get("scrollHeight")
        client_height = overflow.get("clientHeight")
        if scroll_height is not None and client_height is not None:
            if scroll_height - client_height > GEOMETRY_TOLERANCE_PX:
                reasons.append(
                    f"content height {_fmt(scroll_height)} exceeds box height {_fmt(client_height)}"
                )

    if element.parent_id is not None:
        parent = measurement.by_id[element.parent_id]
        if parent.overflow.get("hidden") and not _contains(parent.rect, rect):
            reasons.append(
                f"element box is not contained by clipping ancestor {parent.id!r}"
            )

    if element.text:
        if rect.w <= GEOMETRY_TOLERANCE_PX or rect.h <= GEOMETRY_TOLERANCE_PX:
            reasons.append("text box has no measurable area (invisible text)")
        line_height = element.styles.get("lineHeight")
        if line_height is not None and rect.h + GEOMETRY_TOLERANCE_PX < line_height:
            reasons.append(
                f"text box height {_fmt(rect.h)} is shorter than line-height {_fmt(line_height)}"
            )
    return reasons


def _check_clipping(measurement: Measurement) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for element in measurement.elements:
        reasons = _clipping_reasons(element, measurement)
        if not reasons:
            continue
        findings.append(
            _finding(
                RULE_CLIPPING,
                element.id,
                "; ".join(reasons),
                evidence={
                    "role": element.role,
                    "rect": _rect_payload(element.rect),
                    "reasons": reasons,
                },
            )
        )
    return findings


def _check_overlap(measurement: Measurement) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    elements = [element for element in measurement.elements if element.interactive]
    for index, first in enumerate(elements):
        for second in elements[index + 1:]:
            intersection = _intersection(first.rect, second.rect)
            if intersection is None:
                continue
            if (
                intersection.w <= GEOMETRY_TOLERANCE_PX
                or intersection.h <= GEOMETRY_TOLERANCE_PX
            ):
                continue
            # Fully nested targets are treated as intentional composition (legal
            # negative); only partial intersections are mis-tap risks.
            if _contains(first.rect, second.rect) or _contains(second.rect, first.rect):
                continue
            left, right = sorted((first.id, second.id))
            findings.append(
                _finding(
                    RULE_OVERLAP,
                    left,
                    (
                        f"interactive targets {left!r} and {right!r} overlap by "
                        f"{_fmt(intersection.w)}x{_fmt(intersection.h)} CSS px"
                    ),
                    related_element_id=right,
                    evidence={
                        "intersection": _rect_payload(intersection),
                        "first_rect": _rect_payload(first.rect),
                        "second_rect": _rect_payload(second.rect),
                    },
                )
            )
    return findings


def _check_contrast(measurement: Measurement) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for element in measurement.elements:
        if not element.text:
            continue
        color = element.styles.get("color")
        if color is None:
            continue
        background = _effective_background(element, measurement)
        font_size = element.styles.get("fontSize")
        font_weight = element.styles.get("fontWeight", DEFAULT_FONT_WEIGHT)
        large_text = is_large_text(font_size, font_weight) if font_size is not None else False
        threshold = CONTRAST_LARGE_MIN if large_text else CONTRAST_NORMAL_MIN
        ratio = contrast_ratio(color, background)
        if round(ratio, 2) >= threshold:
            continue
        findings.append(
            _finding(
                RULE_CONTRAST,
                element.id,
                (
                    f"text contrast {round(ratio, 2)}:1 is below WCAG 2.2 AA "
                    f"{threshold}:1 ({'large' if large_text else 'normal'} text, "
                    f"font-size {_fmt(font_size) if font_size is not None else 'unknown'} px)"
                ),
                evidence={
                    "foreground": "#" + "".join(f"{channel:02x}" for channel in color),
                    "background": "#" + "".join(f"{channel:02x}" for channel in background),
                    "ratio": round(ratio, 2),
                    "threshold": threshold,
                    "font_size_px": font_size,
                    "font_weight": font_weight,
                    "large_text": large_text,
                },
            )
        )
    return findings


def _check_focus(measurement: Measurement) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for element in measurement.elements:
        if not element.interactive:
            continue
        styles = element.styles
        if "focusVisible" not in styles:
            continue
        if styles["focusVisible"] is False:
            findings.append(
                _finding(
                    RULE_FOCUS,
                    element.id,
                    "keyboard focus has no visible indicator (focusVisible=false)",
                    evidence={"role": element.role, "focusVisible": False},
                )
            )
            continue
        focus_color = styles.get("focusColor")
        if focus_color is None:
            continue
        background = _ancestor_background(element, measurement)
        ratio = contrast_ratio(focus_color, background)
        if round(ratio, 2) >= FOCUS_CONTRAST_MIN:
            continue
        findings.append(
            _finding(
                RULE_FOCUS,
                element.id,
                (
                    f"focus ring contrast {round(ratio, 2)}:1 is below "
                    f"{FOCUS_CONTRAST_MIN}:1"
                ),
                evidence={
                    "focus_color": "#" + "".join(f"{channel:02x}" for channel in focus_color),
                    "background": "#" + "".join(f"{channel:02x}" for channel in background),
                    "ratio": round(ratio, 2),
                    "threshold": FOCUS_CONTRAST_MIN,
                },
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def probe(measurement: dict[str, Any]) -> dict[str, Any]:
    """Run the Stage 1 geometry probe on a measurement document.

    The result is always ``runtime_level: SIMULATED``; a measurement document
    cannot upgrade itself to native evidence (Stage 3 owns that).
    """
    _verify_probe_ownership()
    normalized = normalize_measurement(measurement)
    findings: list[dict[str, Any]] = []
    findings.extend(_check_target_size(normalized))
    findings.extend(_check_clipping(normalized))
    findings.extend(_check_overlap(normalized))
    findings.extend(_check_contrast(normalized))
    findings.extend(_check_focus(normalized))
    findings.sort(
        key=lambda finding: (
            finding["rule_id"],
            finding["element_id"],
            finding.get("related_element_id", ""),
            finding["message"],
        )
    )
    summary = {
        "fail": sum(1 for finding in findings if finding["severity"] == "FAIL"),
        "warning": sum(1 for finding in findings if finding["severity"] == "WARNING"),
        "info": sum(1 for finding in findings if finding["severity"] == "INFO"),
        "elements": len(normalized.elements),
        "interactive_elements": sum(1 for element in normalized.elements if element.interactive),
        "rules_evaluated": list(SUPPORTED_RULES),
    }
    return {
        "ok": summary["fail"] == 0,
        "probe_id": PROBE_ID,
        "mode": PROBE_MODE,
        "runtime_level": RUNTIME_LEVEL,
        "viewport": dict(normalized.viewport),
        "findings": findings,
        "summary": summary,
    }


def probe_file(path: str | Path) -> dict[str, Any]:
    """Load a UTF-8 JSON measurement document and probe it."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return probe(payload)
