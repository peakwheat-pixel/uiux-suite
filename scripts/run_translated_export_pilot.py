"""Run the product's acceptance pipeline to create a real translated artifact,
then export the same chapter as PNG and ZIP through the product export service.

This uses the New Manga acceptance bridge (mock/local providers) that the
product ships for its frozen M2-AC1 acceptance loop. It does not modify the
product source and writes only to an isolated data root under testdata/.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

APP = Path(r"G:\AI\uiux-workbench-copy")
EVIDENCE = Path(r"G:\AI\universal-uiux-engineering\evidence\T5.3")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def call(proc, request_id: int, method: str, params: dict | None = None) -> dict:
    payload = {"id": request_id, "method": method, "params": params or {}}
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"bridge closed while waiting for {method}")
    return json.loads(line)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data_root = APP / "testdata" / f"acceptance-export-{stamp}"
    data_root.mkdir(parents=True, exist_ok=False)
    catalog_db = data_root / "catalog.sqlite"
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(APP / "src"),
            "M2AC1_TEST_MODE": "1",
            "NEWMANGA_DATA_ROOT": str(data_root),
            "M2RC2_CATALOG_DB": str(catalog_db),
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    stderr_file = data_root / "bridge-stderr.log"
    with stderr_file.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(
            [sys.executable, "-m", "bootstrap.acceptance_bridge"],
            cwd=str(APP),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        transcript = []
        try:
            for rid, method, params in [
                (1, "ping", {}),
                (2, "seed_fixture", {}),
                (3, "run_pipeline", {}),
                (4, "saved_summary", {}),
                (5, "reader_pages", {}),
                (6, "export_page", {"page_index": 0}),
                (7, "export_page", {"page_index": 1}),
            ]:
                response = call(proc, rid, method, params)
                transcript.append({"request": {"id": rid, "method": method, "params": params}, "response": response})
                if "error" in response:
                    raise RuntimeError(f"{method} failed: {response['error']}")
            shutdown = call(proc, 8, "shutdown", {})
            transcript.append({"request": {"id": 8, "method": "shutdown", "params": {}}, "response": shutdown})
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()

    # Re-open the SAME persisted state via the product assembly, then exercise
    # the production ZIP export service over the translated pages.
    sys.path.insert(0, str(APP / "src"))
    os.environ.update(
        {
            "NEWMANGA_DATA_ROOT": str(data_root),
            "M2RC2_CATALOG_DB": str(catalog_db),
            "QT_QPA_PLATFORM": "offscreen",
        }
    )
    from application.export.service import ExportFormat, ExportPage, ExportRequest, OverwritePolicy, StalePolicy
    from bootstrap.acceptance_bridge import assemble_acceptance_core

    core = assemble_acceptance_core(data_root / "library.db", data_root / "managed")
    books = core.repository.list_books()
    chapters = core.repository.list_chapters(books[0].book_id)
    chapter_id = chapters[0].chapter_id
    reader_pages = core.reader_catalog.list_pages(chapter_id)
    if any(not page.translated_path for page in reader_pages):
        raise RuntimeError("acceptance pipeline did not produce translated pages")
    export_pages = []
    for page in reader_pages:
        original = Path(page.original_path)
        translated = Path(page.translated_path)
        export_pages.append(
            ExportPage(
                page_id=page.page_id,
                filename=page.filename,
                source_provider=lambda p=original: p.read_bytes(),
                translated_provider=lambda p=translated: p.read_bytes(),
                translated_revision_id=page.translated_revision_id,
                current_translated_revision_id=page.current_translated_revision_id,
            )
        )
    zip_path = data_root / "exports" / "acceptance-export.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    result = core.export_service.export(
        ExportRequest(
            book_id=books[0].book_id,
            chapter_id=chapter_id,
            format=ExportFormat.ZIP,
            output_path=zip_path,
            pages=tuple(export_pages),
            mode="translated",
            overwrite_policy=OverwritePolicy.OVERWRITE,
            stale_policy=StalePolicy.ABORT,
        )
    )

    pngs = []
    for page_index in (0, 1):
        p = data_root / "exports" / f"m2ac1-export-page-{page_index + 1}.png"
        pngs.append({"path": str(p.relative_to(data_root)), "sha256": sha(p), "size": p.stat().st_size})
    zip_entries = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            zip_entries.append({"name": info.filename, "size": info.file_size, "crc": info.CRC})

    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.3-TRANSLATED-EXPORT",
        "kind": "tool_log",
        "runtime_level": "NATIVE_APP",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product": {"path": str(APP), "source_unchanged": True},
        "data_root": str(data_root),
        "procedure": {
            "bridge": "python -m bootstrap.acceptance_bridge (M2AC1_TEST_MODE=1, mock/local providers)",
            "pipeline": "seed_fixture -> run_pipeline (translate_all, m2ac1-mock-ocr/translate)",
            "png": "bridge export_page 0/1 via product ExportService",
            "zip": "production ExportService.export(ExportFormat.ZIP) over the persisted translated revisions",
        },
        "transcript": transcript,
        "persisted": {
            "books": len(books),
            "chapters": len(chapters),
            "pages": len(reader_pages),
            "translated_pages": sum(1 for page in reader_pages if page.translated_path),
            "run_status": transcript[2]["response"].get("result", {}).get("status"),
        },
        "png_exports": pngs,
        "zip_export": {
            "path": str(zip_path.relative_to(data_root)),
            "sha256": sha(zip_path),
            "size": zip_path.stat().st_size,
            "export_id": result.export_id,
            "status": str(result.status),
            "entries": zip_entries,
        },
        "limitations": [
            "Synthetic acceptance fixture (2 deterministic pages), not production manga data.",
            "Mock/local pipeline providers supplied by the product's acceptance bridge; no external translation service was used.",
            "The ZIP export is invoked through the production ExportService API after persisting the translated revisions; it is not a Tauri-dialog click.",
        ],
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "translated-export.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "data_root": str(data_root), "png": pngs, "zip": evidence["zip_export"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
