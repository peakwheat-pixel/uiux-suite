"""PySide6/QPA real measurements (T3.3).

This module measures the *actual* Qt platform plugin in use. It never upgrades
an offscreen/software result to NATIVE; `runtime_level` reflects the QPA name.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def available() -> bool:
    try:
        import PySide6  # noqa: F401
    except Exception:  # pragma: no cover - optional dependency
        return False
    return True


def measure(screenshot: str | Path | None = None) -> dict[str, Any]:
    if not available():
        return {"ok": False, "runtime_level": "UNAVAILABLE", "reason": "PySide6 not installed"}
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QSplitter, QVBoxLayout, QWidget

    app = QApplication.instance() or QApplication([])
    screen = app.primaryScreen()
    dpi = float(screen.logicalDotsPerInch())
    dpr = float(screen.devicePixelRatio())
    geometry = screen.geometry()
    fonts = QFontDatabase.families()
    has_yahei = QFontDatabase.hasFamily("Microsoft YaHei") or QFontDatabase.hasFamily("Microsoft YaHei UI")

    window = QWidget()
    layout = QVBoxLayout(window)
    label = QLabel("中文界面 DPI 验证")
    label.setFont(QFont("Microsoft YaHei", 12))
    edit = QLineEdit()
    edit.setPlaceholderText("搜索订单")
    splitter = QSplitter(Qt.Horizontal)
    splitter.addWidget(QLabel("左"))
    splitter.addWidget(QLabel("右"))
    layout.addWidget(label)
    layout.addWidget(edit)
    layout.addWidget(splitter)
    window.resize(640, 360)
    window.show()
    app.processEvents()

    metric = label.fontMetrics()
    focus = {
        "label": int(label.focusPolicy().value),
        "edit": int(edit.focusPolicy().value),
        "edit_focusable": edit.focusPolicy() != Qt.NoFocus,
    }
    result: dict[str, Any] = {
        "ok": True,
        "runtime_level": "NATIVE_QPA" if app.platformName() == "windows" else app.platformName().upper(),
        "platform": app.platformName(),
        "qt_version": __import__("PySide6.QtCore", fromlist=["qVersion"]).qVersion(),
        "screen": {"dpi": dpi, "device_pixel_ratio": dpr, "width": geometry.width(), "height": geometry.height()},
        "fonts": {"count": len(fonts), "cjk_yahei": has_yahei},
        "metrics": {
            "label_size_hint": [label.sizeHint().width(), label.sizeHint().height()],
            "label_font_height": metric.height(),
            "edit_height": edit.sizeHint().height(),
            "window_size": [window.width(), window.height()],
        },
        "focus": focus,
        "scale_factor_env": os.environ.get("QT_SCALE_FACTOR", "1"),
    }
    if screenshot:
        path = Path(screenshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        pixmap = window.grab()
        pixmap.save(str(path), "PNG")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result["screenshot"] = {"path": str(path), "sha256": digest, "size": [pixmap.width(), pixmap.height()]}
    window.close()
    app.processEvents()
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    screenshot = None
    if "--screenshot" in args:
        index = args.index("--screenshot")
        screenshot = args[index + 1]
        del args[index : index + 2]
    result = measure(screenshot)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
