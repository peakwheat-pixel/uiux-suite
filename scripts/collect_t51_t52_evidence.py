"""Collect evidence for the real New Manga isolated pilot (T5.1/T5.2/T5.3)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"G:\AI\universal-uiux-engineering")
SRC = Path(r"G:\CODEX\New Manga")
COPY = Path(r"G:\AI\uiux-workbench-copy")
OUT = REPO / "evidence"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(path), capture_output=True, text=True, encoding="utf-8").stdout.strip()


def stats(root: Path) -> tuple[int, int]:
    files = [p for p in root.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files if p.exists())


def main() -> int:
    generated = datetime.now(timezone.utc).isoformat()
    source_baseline = json.loads((OUT / "T5.1/source-baseline.json").read_text(encoding="utf-8"))
    head = git(SRC, "rev-parse", "HEAD")
    source_dirty = bool(git(SRC, "status", "--porcelain"))
    source_unchanged = head == source_baseline["git"]["head"] and source_dirty == source_baseline["git"]["dirty"]
    src_files, src_bytes = stats(SRC)
    copy_files, copy_bytes = stats(COPY)
    db_path = Path.home() / "AppData" / "Roaming" / "com.newmanga.m2rc1.desktop" / "data" / "library.db"
    db_counts = {}
    if db_path.is_file():
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for table in ("books", "chapters", "pages"):
                try:
                    db_counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    db_counts[table] = None
        finally:
            con.close()
    baseline = json.loads((OUT / "T5.1/baseline-dom.json").read_text(encoding="utf-8"))
    after = json.loads((OUT / "T5.1/after-dom.json").read_text(encoding="utf-8"))
    before_metrics = {p["name"]: {"buttons": p["buttonCount"], "too_small": len(p["tooSmallButtons"]), "min_font": p["minFont"], "overflow": p["hasHorizontalOverflow"], "focus_outline": (p.get("focus") or {}).get("outline")} for p in baseline["pages"]}
    after_metrics = {p["name"]: {"buttons": p["buttonCount"], "too_small": len(p["tooSmallButtons"]), "min_font": p["minFont"], "overflow": p["hasHorizontalOverflow"], "focus_outline": (p.get("focus") or {}).get("outline")} for p in after["pages"]}

    def shot(rel: str) -> dict:
        p = OUT / rel
        return {"path": rel, "sha256": sha256(p) if p.is_file() else None, "size": p.stat().st_size if p.is_file() else None}

    t51 = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.1-REAL-APP-PILOT",
        "kind": "tool_log",
        "runtime_level": "NATIVE_APP",
        "generated_at": generated,
        "source": {"path": str(SRC), "git_head": head, "dirty": source_dirty, "unchanged": source_unchanged, "files": src_files, "bytes": src_bytes},
        "isolated_copy": {"path": str(COPY), "files": copy_files, "bytes": copy_bytes, "same_file_count": copy_files == src_files, "same_bytes": copy_bytes == src_bytes, "app_exe_sha256": sha256(COPY / "apps/desktop/src-tauri/target/release/m2rc1-desktop.exe"), "git_status_sample": git(COPY, "status", "--porcelain").splitlines()[:20]},
        "launch": {"title": "M2-RC1 resource channel runtime", "mode": "packaged core-sidecar", "cdp": "WebView2 --remote-debugging-port=9222 (test-only config)", "uia_elements": 14, "dom_page_text_chars": len(baseline["pages"][0]["bodyText"])},
        "baseline": {"pages": before_metrics, "console_errors": baseline.get("consoleErrors", []), "screenshots": [shot("T5.1/baseline-bookshelf.png"), shot("T5.1/baseline-workbench.png"), shot("T5.1/baseline-reader.png"), shot("T5.1/baseline-settings.png")]},
        "real_flows": {
            "create_book": {"title": "DSH 娴嬭瘯浣滃搧", "note": "CJK title displayed mojibake in UI; underlying IPC stored the same string"},
            "create_chapter": {"chapter": "Chapter 1", "chapter_id": "89a26b829f824bb09005a71e2886df8f"},
            "import_folder": {"folder": "testdata/manga-demo/ch01", "imported": 3, "skipped": 0, "rejected": 0, "book_page_count": 3, "native_picker": "UIA folder picker, path set via ValuePattern"},
            "duplicate_import": {"imported": 0, "skipped": 3, "rejected": 0, "book_page_count": 3},
            "reader": {"start": "1 / 3", "after_next": "2 / 3", "after_next_2": "3 / 3", "image_loaded": True},
            "export": {"attempted_formats": ["png", "zip"], "result": "FAILED", "codes": ["INVALID_REQUEST", "EXPORT_INPUT_UNAVAILABLE"], "reason": "export requires translated_path/artifact; pages are unprocessed in this pilot"},
            "undo_redo": {"result": "NOT_AVAILABLE", "reason": "RC2 exposes no undo/redo model; region writes are gated GAP-G9/G12/G13"},
        },
        "screenshots": [shot("T5.1/real-bookshelf-with-data.png"), shot("T5.1/real-reader-page1.png"), shot("T5.2/after-workbench-real.png")],
        "generator": {"path": "scripts/collect_t51_t52_evidence.py", "sha256": sha256(Path(__file__))},
        "limitations": [
            "App data (library.db) lives in the packaged default profile; the copy itself is isolated but the profile was not fully isolated.",
            "The binary was rebuilt in the isolated copy with a CDP test flag; production package is unchanged.",
            "Export and undo/redo were not accepted by the product path; recorded as limitations, not PASS.",
            "This is one synthetic 3-page title, not production data.",
        ],
    }
    (OUT / "T5.1/real-app-pilot.json").write_text(json.dumps(t51, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    t52 = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.2-BEFORE-AFTER",
        "kind": "tool_log",
        "runtime_level": "NATIVE_APP",
        "generated_at": generated,
        "changes": [
            {"file": "apps/desktop/frontend/src/theme/global.css", "summary": "focus-visible ring, 32px controls, 12/14px typography, scrollbar and disabled contrast"},
            {"file": "apps/desktop/frontend/src/theme/tokens.ts", "summary": "base 13→14, badge 10→11, secondary 11→12, rail 64→72, toolbar 48→56"},
            {"file": "apps/desktop/frontend/src/shell/AppShell.tsx", "summary": "nav labels 10→12px and icons 18→20px"},
            {"file": "apps/desktop/frontend/src/workbench/WorkbenchToolbar.tsx", "summary": "two-row grouped toolbar, primary/secondary actions, disabled capabilities collapsed under details"},
            {"file": "apps/desktop/frontend/src/bookshelf/EmptyStateBookshelf.tsx", "summary": "3-step onboarding, keyboard hint, clearer hierarchy"},
            {"file": "apps/desktop/frontend/src/bookshelf/ImportDialog.tsx", "summary": "auto-preselect single book/chapter, enable target select and folder picker"},
        ],
        "before": before_metrics,
        "after": after_metrics,
        "screenshots": [shot("T5.2/baseline-bookshelf.png"), shot("T5.2/after-bookshelf.png"), shot("T5.2/baseline-workbench.png"), shot("T5.2/after-workbench.png")],
        "functional_regression": {"nav_pages": ["bookshelf", "workbench", "reader", "settings"], "console_errors": 0, "create_book": True, "create_chapter": True, "import_folder": True, "duplicate_import": True, "reader_next_pages": True, "export": "FAILED (product translated-input requirement)", "undo_redo": "NOT_AVAILABLE"},
        "ux_findings": [
            "After import the book/chapter counts stayed stale until reload (fixed by manual refresh only; not patched in RC2).",
            "CJK title entered through Playwright appeared mojibake in the rendered UI; root cause not isolated.",
            "Import dialog target book was disabled from the detail panel; fixed by preselecting the single book/chapter.",
            "Export requires a translated artifact; untranslated pages correctly fail closed with EXPORT_INPUT_UNAVAILABLE.",
        ],
        "limitations": ["No production user task observation; one synthetic title.", "No accessibility tree/runtime AT validation of the redesign."],
    }
    (OUT / "T5.2/before-after.json").write_text(json.dumps(t52, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    t53 = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.3-DATA-SAFETY",
        "kind": "tool_log",
        "runtime_level": "OS_INTEGRATION",
        "generated_at": generated,
        "source_unchanged": {"head": head, "dirty": source_dirty, "unchanged_vs_baseline": source_unchanged, "files": src_files, "bytes": src_bytes},
        "isolated_copy": {"path": str(COPY), "files": copy_files, "bytes": copy_bytes, "same_bytes": copy_bytes == src_bytes},
        "database": {"path": str(db_path), "exists": db_path.is_file(), "size": db_path.stat().st_size if db_path.is_file() else None, "sha256": sha256(db_path) if db_path.is_file() else None, "counts": db_counts},
        "cancel": {"result": "PASS", "message": "用户取消了文件夹选择。", "page_count_after": 3},
        "duplicate_policy": {"result": "PASS", "imported": 0, "skipped": 3, "page_count_after": 3},
        "export": {"result": "FAILED_CLOSED", "codes": ["INVALID_REQUEST", "EXPORT_INPUT_UNAVAILABLE"], "reason": "pages have no translated artifact; product refused export"},
        "undo_redo": {"result": "NOT_AVAILABLE", "reason": "no undo model in RC2; region writes gated"},
        "git_rollback_drill": {"result": "PENDING", "note": "to be executed on isolated copy with a reversible commit/revert"},
        "generator": {"path": "scripts/collect_t51_t52_evidence.py", "sha256": sha256(Path(__file__))},
        "limitations": ["Export PASS cannot be claimed without a translated page; this is a product-path prerequisite, not a tool failure.", "Library data lives in the packaged default profile for this pilot."],
    }
    (OUT / "T5.3/data-safety.json").write_text(json.dumps(t53, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "source_unchanged": source_unchanged, "db_counts": db_counts, "before": before_metrics, "after": after_metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
