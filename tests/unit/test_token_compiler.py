from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

from uiux_engine import design_system, token_compiler

TOKENS = design_system.load_tokens()


def test_css_contains_resolved_variables():
    css = token_compiler.to_css(TOKENS)
    assert ":root {" in css
    assert "--color-bg-canvas:" in css
    assert "--space-1: 4px;" in css
    assert "var(--color-neutral" not in css


def test_tailwind_is_parseable_js_like():
    text = token_compiler.to_tailwind(TOKENS)
    assert text.startswith("module.exports = ")
    payload = json.loads(text[len("module.exports = ") :].rstrip(";\n"))
    assert "colors" in payload["theme"]["extend"]
    assert payload["theme"]["extend"]["spacing"]["space-1"] == "4px"


def test_pyside6_module_is_importable(tmp_path: Path):
    out = tmp_path / "tokens_generated.py"
    out.write_text(token_compiler.to_pyside6(TOKENS), encoding="utf-8")
    namespace: dict = {}
    exec(compile(out.read_text(encoding="utf-8"), str(out), "exec"), namespace)
    assert namespace["COLORS"]["color-bg-canvas"]
    assert "QWidget" in namespace["QSS"]
    assert "QPushButton" in namespace["QSS"]


def test_alias_resolution():
    tokens = {
        "schema_version": "1.3.3",
        "token_set_version": "1.0",
        "theme": "light",
        "colors": {"color-base": "#112233", "color-alias": "var(--color-base)"},
        "spacing": {"space-1": 4},
        "typography": {"body": {"fontSize": 14, "lineHeight": 1.5}},
    }
    css = token_compiler.to_css(tokens)
    assert "--color-alias: #112233;" in css


def test_alias_cycle_is_rejected():
    tokens = {
        "schema_version": "1.3.3",
        "token_set_version": "1.0",
        "theme": "light",
        "colors": {"color-a": "var(--color-a)"},
        "spacing": {"space-1": 4},
        "typography": {"body": {"fontSize": 14, "lineHeight": 1.5}},
    }
    with pytest.raises(ValueError):
        token_compiler.to_css(tokens)


def test_compile_all_formats_deterministic(tmp_path: Path):
    for fmt in ("css", "tailwind", "pyside6"):
        first = token_compiler.compile_tokens(fmt, tmp_path / f"a-{fmt}", TOKENS).read_text(encoding="utf-8")
        second = token_compiler.compile_tokens(fmt, tmp_path / f"b-{fmt}", TOKENS).read_text(encoding="utf-8")
        assert first == second


def test_cli_tokens_exports_css(tmp_path: Path):
    out = tmp_path / "tokens.css"
    env = {"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "uiux_engine.cli", "tokens", "--format", "css", "--out", str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **env},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.is_file()
    assert ":root {" in out.read_text(encoding="utf-8")
