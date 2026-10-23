"""Design-token compilers: CSS variables, Tailwind config, PySide6 QSS/module (T2.3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import design_system


def _tokens(tokens: dict[str, Any] | None) -> dict[str, Any]:
    tokens = tokens or design_system.load_tokens()
    problems = design_system.token_schema_errors(tokens)
    if problems:
        raise ValueError("; ".join(problems))
    return tokens


def _resolve(value: Any, colors: dict[str, str], typography: dict[str, Any], seen: tuple[str, ...] = ()) -> str:
    if not isinstance(value, str):
        return str(value)
    if value.startswith("var(--") and value.endswith(")"):
        name = value[6:-1]
        if name in seen:
            raise ValueError(f"token alias cycle: {' -> '.join(seen + (name,))}")
        if name in colors and isinstance(colors[name], str):
            return _resolve(colors[name], colors, typography, seen + (name,))
    return value


def _css_length(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value}px"
    return str(value)


def to_css(tokens: dict[str, Any] | None = None) -> str:
    data = _tokens(tokens)
    colors = data["colors"]
    lines = [":root {"]
    for name, value in colors.items():
        lines.append(f"  --{name}: {_resolve(value, colors, {})};")
    for name, value in data["spacing"].items():
        lines.append(f"  --{name}: {_css_length(value)};")
    for name, spec in data["typography"].items():
        lines.append(f"  --font-{name}-size: {spec['fontSize']}px;")
        lines.append(f"  --font-{name}-line-height: {spec['lineHeight']};")
        if "fontWeight" in spec:
            lines.append(f"  --font-{name}-weight: {spec['fontWeight']};")
    for name, value in data.get("radii", {}).items():
        lines.append(f"  --{name}: {value}px;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_tailwind(tokens: dict[str, Any] | None = None) -> str:
    data = _tokens(tokens)
    colors: dict[str, str] = {}
    stack = list(data["colors"].items())
    while stack:
        name, value = stack.pop(0)
        resolved = _resolve(value, data["colors"], {})
        if resolved.startswith("var(--"):
            continue
        colors[name] = resolved
    theme = {
        "colors": colors,
        "spacing": {name: _css_length(value) for name, value in data["spacing"].items()},
        "fontSize": {
            name: [f"{spec['fontSize']}px", {"lineHeight": str(spec["lineHeight"])}]
            for name, spec in data["typography"].items()
        },
        "borderRadius": {name: f"{value}px" for name, value in data.get("radii", {}).items()},
    }
    return "module.exports = " + json.dumps({"theme": {"extend": theme}}, ensure_ascii=False, indent=2) + ";\n"


def to_pyside6(tokens: dict[str, Any] | None = None) -> str:
    data = _tokens(tokens)
    colors = {
        name: _resolve(value, data["colors"], {})
        for name, value in data["colors"].items()
        if not _resolve(value, data["colors"], {}).startswith("var(--")
    }
    spacing = {name: _css_length(value) for name, value in data["spacing"].items()}
    typography = {
        name: {"fontSize": spec["fontSize"], "lineHeight": spec["lineHeight"], "fontWeight": spec.get("fontWeight", 400)}
        for name, spec in data["typography"].items()
    }
    radii = {name: float(value) for name, value in data.get("radii", {}).items()}
    qss = "\n".join(
        [
            "/* Generated from design tokens; do not edit by hand. */",
            f'QWidget {{ background-color: {colors.get("bg-canvas", "#ffffff")}; color: {colors.get("fg-primary", "#1f2328")}; }}',
            f'QPushButton {{ border-radius: {radii.get("sm", 4)}px; padding: {spacing.get("space-2", "8px")}; }}',
            f'QLineEdit {{ border-radius: {radii.get("sm", 4)}px; padding: {spacing.get("space-1", "4px")}; }}',
        ]
    )
    payload = {"COLORS": colors, "SPACING": spacing, "TYPOGRAPHY": typography, "RADII": radii, "QSS": qss}
    lines = [
        '"""Generated from design tokens; do not edit by hand."""',
        "",
        f"COLORS = {json.dumps(payload['COLORS'], ensure_ascii=False, indent=2, sort_keys=True)}",
        f"SPACING = {json.dumps(payload['SPACING'], ensure_ascii=False, indent=2, sort_keys=True)}",
        f"TYPOGRAPHY = {json.dumps(payload['TYPOGRAPHY'], ensure_ascii=False, indent=2, sort_keys=True)}",
        f"RADII = {json.dumps(payload['RADII'], ensure_ascii=False, indent=2, sort_keys=True)}",
        f"QSS = {json.dumps(payload['QSS'], ensure_ascii=False)}",
        "",
    ]
    return "\n".join(lines)


COMPILERS = {"css": to_css, "tailwind": to_tailwind, "pyside6": to_pyside6}


def compile_tokens(fmt: str, out: str | Path, tokens: dict[str, Any] | None = None) -> Path:
    if fmt not in COMPILERS:
        raise ValueError(f"unknown format: {fmt}")
    content = COMPILERS[fmt](tokens)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
