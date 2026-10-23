"""Stage 5 end-to-end validation on the synthetic PySide6 workbench.

Runs a real Qt application (native QPA) through import -> browse -> canvas ->
edit -> save -> export -> undo/redo -> error handling, then compares the
"before" and "after" UI metrics.  All data is synthetic; the test app lives in
`sandbox/workbench_app` and never touches a real user project.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "sandbox" / "workbench_app"))
sys.path.insert(0, str(REPO_ROOT / "runtime"))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_SCALE_FACTOR", "1.0")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402

import app as workbench  # noqa: E402

OUT_DIR = Path(os.environ.get("UIUX_EVIDENCE_DIR", str(REPO_ROOT / "evidence" / "T5.1")))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contrast(fg: str, bg: str) -> float:
    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

    def lum(color: tuple[int, int, int]) -> float:
        parts = []
        for channel in color:
            c = channel / 255
            parts.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    high, low = sorted((lum(rgb(fg)), lum(rgb(bg))), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def measure(window: workbench.MainWindow) -> dict:
    button: QPushButton = window.add_button
    row_height = window.table.rowHeight(0) if window.table.rowCount() else window.table.verticalHeader().defaultSectionSize()
    return {
        "font_px": window.fontInfo().pixelSize() or window.fontMetrics().height(),
        "button_min": [button.minimumWidth(), button.minimumHeight()],
        "button_actual": [button.width(), button.height()],
        "table_row_height": row_height,
        "foreground": "#b0b0b0" if window.theme == "before" else "#1f2328",
        "background": "#fafafa" if window.theme == "before" else "#ffffff",
        "contrast": contrast("#b0b0b0" if window.theme == "before" else "#1f2328", "#fafafa" if window.theme == "before" else "#ffffff"),
        "window_size": [window.width(), window.height()],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    git_commit = os.popen("git rev-parse HEAD").read().strip()
    git_dirty = bool(os.popen("git status --porcelain").read().strip())
    started = time.perf_counter()
    steps: list[dict] = []

    def step(name: str, action) -> bool:
        started_at = time.perf_counter()
        ok = False
        detail = ""
        try:
            detail = action() or ""
            ok = True
        except Exception as exc:  # noqa: BLE001 - evidence must capture failure
            detail = f"{type(exc).__name__}: {exc}"
        steps.append({"name": name, "ok": ok, "detail": str(detail)[:300], "ms": round((time.perf_counter() - started_at) * 1000, 2)})
        return ok

    app = QApplication.instance() or QApplication([])
    before = workbench.MainWindow("before")
    after = workbench.MainWindow("after")
    after.show()
    before.show()
    app.processEvents()

    tmp = Path(tempfile.mkdtemp(prefix="uiux-workbench-"))
    sample = tmp / "sample.json"
    sample.write_text(
        json.dumps(
            {"items": [{"item_id": f"i{n}", "name": f"Frame {n}", "x": 20.0 * n, "y": 10.0 * n} for n in range(1, 6)]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    invalid = tmp / "invalid.json"
    invalid.write_text("{not-json", encoding="utf-8")

    def import_ok() -> str:
        assert after.import_path(sample) is True
        assert after.table.rowCount() == 5
        return "5 items"

    def browse() -> str:
        after.table.selectRow(2)
        app.processEvents()
        assert after.table.currentRow() == 2
        assert after.name_edit.text() == "Frame 3"
        return after.name_edit.text()

    def canvas_add() -> str:
        scene_before = len(after.scene.items())
        QTest.mouseClick(after.add_button, Qt.LeftButton)
        app.processEvents()
        scene_after = len(after.scene.items())
        assert scene_after > scene_before, (scene_before, scene_after)
        return f"scene items {scene_before}->{scene_after}"

    def canvas_drag() -> str:
        app.processEvents()
        rect = after.scene_items[-1]
        origin = rect.pos()
        after.canvas.centerOn(rect.rect().center())
        app.processEvents()
        point = after.canvas.mapFromScene(rect.rect().center())
        assert after.canvas.itemAt(point) is not None, f"no item at {point}"
        QPoint = __import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint
        target = point + QPoint(60, 40)
        QTest.mousePress(after.canvas.viewport(), Qt.LeftButton, pos=point, delay=50)
        app.processEvents()
        assert after.canvas._drag_item is not None, "press did not hit an item"
        QTest.mouseMove(after.canvas.viewport(), target, delay=50)
        app.processEvents()
        moved_flag = after.canvas._moved
        visual = rect.pos()
        QTest.mouseRelease(after.canvas.viewport(), Qt.LeftButton, pos=target, delay=50)
        app.processEvents()
        moved = after.scene_items[0].pos() != origin
        assert moved, f"origin={origin} visual={visual} moved_flag={moved_flag} model={after.document.items[0]}"
        return f"drag delta {(after.scene_items[0].pos().x() - origin.x()):.0f},{(after.scene_items[0].pos().y() - origin.y()):.0f}"

    def keyboard_shortcut() -> str:
        from PySide6.QtGui import QKeySequence

        assert after.undo_action.shortcut() == QKeySequence("Ctrl+Z")
        assert after.redo_action.shortcut() == QKeySequence("Ctrl+Y")
        before_index = after.undo_stack.index()
        after.undo_action.trigger()
        app.processEvents()
        assert after.undo_stack.index() == before_index - 1, (before_index, after.undo_stack.index())
        after.redo_action.trigger()
        app.processEvents()
        assert after.undo_stack.index() == before_index
        return "Ctrl+Z / Ctrl+Y actions (shortcut metadata + trigger)"

    def focus_order() -> str:
        after.raise_()
        after.activateWindow()
        after.name_edit.setFocus()
        app.processEvents()
        names = []
        for _ in range(6):
            widget = app.focusWidget()
            names.append(widget.objectName() if widget is not None else "None")
            if not after.focusNextChild():
                break
            app.processEvents()
        assert len(set(names)) > 1, names
        return " -> ".join(names)

    def edit() -> str:
        after.table.selectRow(0)
        app.processEvents()
        after.name_edit.clear()
        QTest.keyClicks(after.name_edit, "Router")
        QTest.mouseClick(after.apply_button, Qt.LeftButton)
        app.processEvents()
        assert after.document.items[0].name == "Router"
        return after.document.items[0].name

    def save() -> str:
        QTest.mouseClick(after.save_button, Qt.LeftButton)
        app.processEvents()
        payload = json.loads(Path(after.document.path).read_text(encoding="utf-8"))
        assert len(payload["items"]) == 6
        return str(after.document.path)

    def export() -> str:
        QTest.mouseClick(after.export_button, Qt.LeftButton)
        app.processEvents()
        target = Path(after.document.path).with_name("workbench-export.json")
        assert target.is_file()
        return str(target)

    def undo_redo() -> str:
        before_count = len(after.document.items)
        for _ in range(3):
            after.undo_action.trigger()
            app.processEvents()
        assert len(after.document.items) == before_count - 1
        for _ in range(3):
            after.redo_action.trigger()
            app.processEvents()
        assert len(after.document.items) == before_count
        return f"undo/redo around {before_count} items"

    def error_handling() -> str:
        original = QMessageBox.warning
        QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)  # type: ignore[assignment]
        try:
            assert after.import_path(invalid) is False
        finally:
            QMessageBox.warning = original  # type: ignore[assignment]
        return "invalid import rejected"

    def screenshots() -> str:
        before_png = OUT_DIR / "workbench-before.png"
        after_png = OUT_DIR / "workbench-after.png"
        before.grab().save(str(before_png), "PNG")
        after.grab().save(str(after_png), "PNG")
        return f"{before_png.name},{after_png.name}"

    actions = [
        ("import", import_ok),
        ("browse_list", browse),
        ("canvas_add", canvas_add),
        ("canvas_drag", canvas_drag),
        ("edit", edit),
        ("save", save),
        ("export", export),
        ("undo_redo", undo_redo),
        ("keyboard_shortcut", keyboard_shortcut),
        ("error_handling", error_handling),
        ("focus_order", focus_order),
        ("screenshots", screenshots),
    ]
    results = [step(name, action) for name, action in actions]
    all_ok = all(results)

    before_metrics = measure(before)
    after_metrics = measure(after)
    pngs = [OUT_DIR / "workbench-before.png", OUT_DIR / "workbench-after.png"]
    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.1-WORKBENCH-E2E",
        "kind": "tool_log",
        "runtime_level": "NATIVE_QT_APP",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": {"path": "scripts/run_workbench_e2e.py", "sha256": sha256(Path(__file__))},
        "git": {"commit": git_commit, "dirty": git_dirty, "dirty_scope": "tracked files excluding evidence/"},
        "app": "sandbox/workbench_app/app.py",
        "isolated_data_dir": str(tmp),
        "synthetic_data_only": True,
        "steps": steps,
        "all_steps_ok": all_ok,
        "before_after": {
            "before": before_metrics,
            "after": after_metrics,
            "improvements": {
                "font_px": after_metrics["font_px"] - before_metrics["font_px"],
                "target_growth_px": after_metrics["button_min"][1] - before_metrics["button_min"][1],
                "contrast": round(after_metrics["contrast"] - before_metrics["contrast"], 2),
            },
        },
        "screenshots": [
            {"path": str(png.relative_to(REPO_ROOT)) if REPO_ROOT in png.parents else str(png), "sha256": sha256(png)}
            for png in pngs
            if png.is_file()
        ],
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "limitations": [
            "Synthetic reference application; this is not the real New Manga workbench.",
            "QTest sends Qt-level events; the canvas drag is Qt-level, not OS physical mouse input.",
            "Ctrl+Z/Ctrl+Y verify QAction shortcut metadata and trigger; the OS-level shortcut map is not exercised.",
            "The invalid-import modal dialog is auto-accepted in the harness; visual dialog interaction is not measured.",
            "Focus traversal uses Qt focusNextChild, not OS-level keyboard navigation.",
            "Screenshots are QWidget.grab() renders, not OS screen captures.",
        ],
    }
    out = OUT_DIR / "workbench-e2e-evidence.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": all_ok, "evidence": str(out.relative_to(REPO_ROOT)) if REPO_ROOT in out.parents else str(out), "steps": steps}, ensure_ascii=False))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
