"""Create one synthetic Region in the isolated New Manga test profile so the
real workbench can exercise its existing retype + 10s undo path.

The profile was created by this pilot and contains only the 3-page synthetic
title. A DB backup is written before the write; the app must be stopped.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(r"G:\AI\uiux-workbench-copy")
DATA = Path(os.environ["APPDATA"]) / "com.newmanga.m2rc1.desktop" / "data"
DB = DATA / "library.db"
MANAGED = DATA / "managed"
OUT = Path(r"G:\AI\universal-uiux-engineering\evidence\T5.3")


def main() -> int:
    if not DB.is_file():
        raise SystemExit(f"missing DB: {DB}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = OUT / f"library-before-region-{stamp}.db"
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, backup)
    sys.path.insert(0, str(APP / "src"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from bootstrap.acceptance_bridge import assemble_acceptance_core
    from domain.regions.entities import BBox, RegionGeometry, RegionOrigin

    core = assemble_acceptance_core(DB, MANAGED)
    books = core.repository.list_books()
    chapters = core.repository.list_chapters(books[0].book_id)
    pages = core.repository.list_pages(chapters[0].chapter_id)
    page = pages[0]
    existing = core.editing.list_regions(page.page_id)
    if existing:
        region = existing[0]
        created = False
    else:
        width = page.width or 600
        height = page.height or 900
        x, y, w, h = 48, 48, min(240, width - 96), min(120, height - 96)
        geometry = RegionGeometry(
            bbox=BBox(x, y, w, h),
            polygon=((x, y), (x + w, y), (x + w, y + h), (x, y + h)),
        )
        region = core.editing.create_region(
            page.page_id, geometry, reading_order=1, origin=RegionOrigin.MACHINE
        )
        created = True
    record = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.3-REGION-FIXTURE",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(DB),
        "db_backup": str(backup),
        "book_id": books[0].book_id,
        "chapter_id": chapters[0].chapter_id,
        "page_id": page.page_id,
        "region_id": region.region_id,
        "region_type": getattr(region, "region_type", None),
        "revision_no": getattr(region, "revision_no", None),
        "created": created,
        "note": "Synthetic test profile only; no production New Manga data touched.",
    }
    (OUT / "region-fixture.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
