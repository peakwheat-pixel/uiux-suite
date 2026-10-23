from __future__ import annotations

from pathlib import Path

from uiux_engine import brownfield, contracts

TOKENS = {
    "schema_version": "1.3.3",
    "token_set_version": "1.0",
    "theme": "light",
    "colors": {"color-fg-primary": "#1f2328", "color-bg-canvas": "#ffffff"},
    "spacing": {"space-1": 4, "space-2": 8},
    "typography": {"body": {"fontSize": 14, "lineHeight": 1.5}},
}


def project(tmp_path: Path, css: str) -> Path:
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "theme.css").write_text(css, encoding="utf-8")
    return root


def test_missing_tokens_are_adopted(tmp_path: Path):
    root = project(tmp_path, ":root { --color-bg-canvas: #ffffff; }")
    report = brownfield.build_report(root, TOKENS)
    assert report["ok"] is True
    actions = {entry["name"]: entry["action"] for entry in report["entries"]}
    assert actions["space-1"] == "ADOPT"
    assert actions["color-bg-canvas"] == "KEEP_LOCAL"


def test_local_override_is_kept(tmp_path: Path):
    root = project(tmp_path, ":root { --color-bg-canvas: #f7f7f7; --color-fg-primary: #1f2328; }")
    report = brownfield.build_report(root, TOKENS)
    entry = next(item for item in report["entries"] if item["name"] == "color-bg-canvas")
    assert entry["action"] == "OVERRIDE"
    assert entry["priority"] == "PROJECT"


def test_safety_conflict_wins(tmp_path: Path):
    root = project(tmp_path, ":root { --color-fg-primary: #eeeeee; --color-bg-canvas: #ffffff; }")
    report = brownfield.build_report(root, TOKENS)
    assert report["ok"] is False
    entry = next(item for item in report["entries"] if item["name"] == "color-fg-primary")
    assert entry["action"] == "CONFLICT"
    assert entry["priority"] == "SUITE"


def test_contrast_calculation():
    assert brownfield.contrast("#000000", "#ffffff") == 21.0
    assert brownfield.contrast("#ffffff", "#ffffff") == 1.0
    assert brownfield.contrast("not-a-color", "#fff") is None


def test_report_is_schema_valid(tmp_path: Path):
    root = project(tmp_path, ":root { --color-bg-canvas: #ffffff; }")
    report = brownfield.build_report(root, TOKENS)
    assert contracts.validation_errors("brownfield-report", report) == []


def test_deterministic(tmp_path: Path):
    root = project(tmp_path, ":root { --space-1: 4px; }")
    assert brownfield.build_report(root, TOKENS) == brownfield.build_report(root, TOKENS)


def test_extract_existing_ignores_unrelated_files(tmp_path: Path):
    root = project(tmp_path, "body { color: red; }")
    (root / "notes.md").write_text("--fake: 1;", encoding="utf-8")
    assert brownfield.extract_existing(root) == {}


def test_no_existing_tokens_adopts_all(tmp_path: Path):
    root = project(tmp_path, "")
    report = brownfield.build_report(root, TOKENS)
    assert report["summary"]["adopted"] == len(report["entries"])
    assert report["ok"] is True
