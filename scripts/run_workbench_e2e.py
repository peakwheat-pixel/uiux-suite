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
        after.undo_action.trigger()
        app.processEvents()
        after.undo_action.trigger()
        app.processEvents()
        assert len(after.document.items) == before_count - 1
        after.redo_action.trigger()
        app.processEvents()
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
        ("edit", edit),
        ("save", save),
        ("export", export),
        ("undo_redo", undo_redo),
        ("error_handling", error_handling),
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
            "QTest sends Qt-level events to widgets; no OS-level physical mouse/keyboard or UIA click-through.",
            "The invalid-import modal dialog is auto-accepted in the harness; visual dialog interaction is not measured.",
            "Screenshots are QWidget.grab() renders, not OS screen captures.",
        ],
    }
    out = OUT_DIR / "workbench-e2e-evidence.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": all_ok, "evidence": str(out.relative_to(REPO_ROOT)) if REPO_ROOT in out.parents else str(out), "steps": steps}, ensure_ascii=False))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
