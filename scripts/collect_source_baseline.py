"""Record read-only baseline of New Manga and start-safe copy manifest (T5.1)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(r"G:\CODEX\New Manga")
OUT = Path(r"G:\AI\universal-uiux-engineering\evidence\T5.1")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=str(SRC), capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(SRC), capture_output=True, text=True, encoding="utf-8").stdout.strip()
    key_files = {}
    for rel in ["README.md", "package.json", "apps/desktop/src-tauri/Cargo.toml", "apps/desktop/src-tauri/tauri.conf.json", "apps/desktop/frontend/package.json"]:
        path = SRC / rel
        if path.is_file():
            key_files[rel] = {"sha256": sha256(path), "size": path.stat().st_size}
    junctions = []
    for p in SRC.rglob("*"):
        try:
            if p.is_symlink() or (p.exists() and getattr(p.stat(), "st_file_attributes", 0) & 0x400):
                junctions.append(str(p.relative_to(SRC)))
        except OSError:
            pass
    report = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.1-SOURCE-BASELINE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(SRC),
        "git": {"head": head, "dirty": bool(git_status), "dirty_entries": git_status[:50], "dirty_count": len(git_status)},
        "key_files": key_files,
        "junctions": junctions,
        "read_only_policy": "No writes, builds, tests or git mutations were executed in the source tree.",
        "generator": {"path": "scripts/collect_source_baseline.py", "sha256": sha256(Path(__file__))},
    }
    (OUT / "source-baseline.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "head": head, "dirty": bool(git_status), "junctions": len(junctions), "key_files": list(key_files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
