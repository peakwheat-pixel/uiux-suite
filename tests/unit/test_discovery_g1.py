"""TASK-02: G1 discovery extraction, inventory reconciliation and freezing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uiux_engine import discovery


def make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    front = root / "apps" / "desktop" / "frontend" / "src"
    rust = root / "apps" / "desktop" / "src-tauri" / "src"
    front.mkdir(parents=True)
    rust.mkdir(parents=True)
    (front / "ReaderPage.tsx").write_text(
        '<main data-testid="page-reader"><div role="dialog" data-testid="reader-settings"></div></main>\n',
        encoding="utf-8",
    )
    (front / "WorkbenchPage.tsx").write_text(
        '<div data-testid="page-workbench"><button data-testid="detail-delete-btn" disabled '
        'title="删除作品（等待能力接入 GAP-G2）"></button></div>\n',
        encoding="utf-8",
    )
    (front / "SettingsPage.tsx").write_text(
        '<button aria-label="保存" aria-describedby="hint" id="gap-g10-create-region">新建</button>\n'
        '<div id="gap-g9-save-manual-translation">x</div>\n',
        encoding="utf-8",
    )
    (front / "PermanentDeleteConfirmDialog.tsx").write_text(
        '<div role="dialog" data-testid="permanent-delete-dialog"></div>\n',
        encoding="utf-8",
    )
    (front / "main.tsx").write_text(
        'import "./theme/global.css";\nReactDOM.createRoot(document.getElementById("root")!);\n',
        encoding="utf-8",
    )
    (rust / "lib.rs").write_text(
        'pub enum TaskStatus { Queued, Running, Failed }\n#[tauri::command]\nfn delete_book() {}\n',
        encoding="utf-8",
    )
    return root


def test_discover_g1_extracts_entities(tmp_path):
    result = discovery.discover_g1(make_tree(tmp_path))
    assert result["summary"]["pages"] >= 2
    assert result["summary"]["dialogs"] >= 2
    assert any(gap["gap"] == "GAP-G2" for gap in result["gaps"])
    assert any("gap-g10-create-region" in row["id"] for row in result["disabled_features"])
    assert "TaskStatus" in result["state_machines"]
    assert result["rust_commands"] == 1
    assert result["a11y"]["count"] >= 2
    assert result["scanned"]["files"] == 6
    assert result["source_binding"]["business_source_dirty"] is False
    assert any(path.endswith("main.tsx") for path in result["source_files"])


def test_freeze_is_stable_and_sensitive(tmp_path):
    root = make_tree(tmp_path)
    first = discovery.discover_g1(root)
    second = discovery.discover_g1(root)
    assert discovery.freeze_discovery(first) == discovery.freeze_discovery(second)
    (root / "apps" / "desktop" / "frontend" / "src" / "Extra.tsx").write_text(
        '<div data-testid="page-extra"></div>', encoding="utf-8")
    third = discovery.discover_g1(root)
    assert discovery.freeze_discovery(third) != discovery.freeze_discovery(first)


def test_reconcile_inventory_states(tmp_path):
    result = discovery.discover_g1(make_tree(tmp_path))
    inventory = {
        "items": [
            {"stable_id": "ITM-PAGE-READER", "declared_scope": "included", "risk_level": "P1"},
            {"stable_id": "ITM-PAGE-SEARCH", "declared_scope": "included", "risk_level": "P2"},
            {"stable_id": "ITM-DIALOG-DELETE", "declared_scope": "included", "risk_level": "P0"},
            {"stable_id": "ITM-UIA-TREE", "declared_scope": "excluded", "risk_level": "P3"},
        ]
    }
    rec = discovery.reconcile_inventory(result, inventory)
    by_id = {row["stable_id"]: row["state"] for row in rec["items"]}
    assert by_id["ITM-PAGE-READER"] == "IMPLEMENTED_FOUND"
    assert by_id["ITM-DIALOG-DELETE"] == "IMPLEMENTED_FOUND"
    assert by_id["ITM-PAGE-SEARCH"] == "NOT_FOUND_IN_SOURCE"
    assert by_id["ITM-UIA-TREE"] == "EXCLUDED_DECLARED"
    assert rec["found"] == 2 and rec["not_found"] == 1 and rec["excluded_declared"] == 1


def test_entry_desktop_matches_source_files(tmp_path):
    result = discovery.discover_g1(make_tree(tmp_path))
    inventory = {"items": [{"stable_id": "ITM-ENTRY-DESKTOP", "declared_scope": "included", "risk_level": "P2"}]}
    rec = discovery.reconcile_inventory(result, inventory)
    assert rec["items"][0]["state"] == "IMPLEMENTED_FOUND"


def test_missing_source_dir_raises(tmp_path):
    with pytest.raises(ValueError):
        discovery.discover_g1(tmp_path / "nope")


@pytest.mark.skipif(not Path(r"G:\AI\uiux-workbench-copy\apps\desktop\frontend\src").is_dir(),
                    reason="isolated New Manga copy not present")
def test_real_workbench_copy_discovery():
    result = discovery.discover_g1(Path(r"G:\AI\uiux-workbench-copy"))
    assert result["scanned"]["files"] > 100
    assert result["summary"]["pages"] > 0
    assert result["summary"]["dialogs"] >= 5
    assert result["summary"]["gaps"] >= 5
    assert len(result["source_binding"]["value"]) == 40
    assert isinstance(result["source_binding"]["business_source_dirty"], bool)
    if result["source_binding"]["business_source_dirty"]:
        assert result["source_binding"]["business_dirty_details"]
    assert result["scanned"]["tree_digest"]
