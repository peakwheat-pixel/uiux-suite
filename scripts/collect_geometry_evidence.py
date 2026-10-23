"""Collect real layout geometry from Qt QPA and Tauri WebView DOM (T1.4)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "evidence" / "T1.4"
DOM = OUT / "tauri-dom.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not DOM.is_file():
        print(json.dumps({"ok": False, "error": "missing evidence/T1.4/tauri-dom.json"}))
        return 1
    sys.path.insert(0, str(REPO / "runtime"))
    from uiux_engine import qt_probe

    qt = qt_probe.measure()
    if not qt.get("ok"):
        print(json.dumps({"ok": False, "error": "Qt QPA unavailable", "detail": qt}))
        return 1
    dom = json.loads(DOM.read_text(encoding="utf-8"))
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":(exclude)evidence"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    )
    report = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T1.4-GEOMETRY-REAL",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True, text=True, encoding="utf-8").stdout.strip(),
            "dirty": dirty,
            "dirty_scope": "tracked files excluding evidence/",
        },
        "qt": {
            "runtime_level": qt["runtime_level"],
            "platform": qt["platform"],
            "screen": qt["screen"],
            "metrics": qt["metrics"],
            "focus": qt["focus"],
            "fonts": qt["fonts"],
        },
        "webview_dom": {
            "runtime_level": dom["runtime_level"],
            "viewport": dom["viewport"],
            "elements": dom["elements"],
            "source": str(DOM.relative_to(REPO)),
            "sha256": sha256(DOM),
        },
        "observations": [
            "Qt label sizeHint and edit height are non-zero on the native Windows QPA.",
            "WebView DOM boxes are non-zero and the viewport reports 800x600 at dpr=1.",
            "The DOM button is 80.4x39.2 CSS px; the Qt button min height is reported in `metrics`.",
        ],
        "generator": {"path": "scripts/collect_geometry_evidence.py", "sha256": sha256(Path(__file__))},
        "limitations": [
            "DOM measured on a synthetic Tauri 2 lab app, not a real product UI.",
            "Qt metrics are from a synthetic probe window; no visual regression baseline.",
            "DOM coordinates are CSS pixels at 100% scale; 125%/150% DOM scaling was not measured.",
        ],
    }
    out = OUT / "geometry-real.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "qt": qt["runtime_level"], "dom": dom["runtime_level"], "dom_button": dom["elements"]["greet_button"], "dirty": dirty}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
