"""Read-only static baseline for an isolated real workbench copy (T5.1 partial)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "evidence" / "T5.1"
WORKBENCH = Path(r"G:\AI\uiux-stage5-sandbox\new-manga-src")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not WORKBENCH.is_dir():
        print(json.dumps({"ok": False, "error": f"missing isolated copy: {WORKBENCH}"}, ensure_ascii=False))
        return 1
    sys.path.insert(0, str(REPO_ROOT / "runtime"))
    from uiux_engine import design_system, discovery, style_linter

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    discovery_report = discovery.discover(WORKBENCH)
    sources = [
        path
        for path in sorted(WORKBENCH.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".tsx", ".ts", ".jsx", ".js", ".css", ".qss", ".scss", ".html"}
        and "node_modules" not in path.parts
    ][:300]
    style_sources = [path for path in sources if path.suffix.lower() in {".tsx", ".ts", ".jsx", ".js", ".css", ".qss", ".scss", ".html"}]
    design_sources = [path for path in sources if path.suffix.lower() in {".css", ".qss", ".tsx", ".jsx"}]
    style = style_linter.lint_files(style_sources, root=WORKBENCH) if style_sources else {"findings": [], "summary": {"fail": 0, "warning": 0, "info": 0}}
    design = design_system.lint_files(design_sources, root=WORKBENCH) if design_sources else {"findings": [], "summary": {"fail": 0, "warning": 0, "info": 0}}
    style_rules = Counter(finding["rule_id"] for finding in style["findings"] if finding.get("rule_id"))
    design_rules = Counter(
        finding.get("rule_id") or finding.get("dimension", "unknown") for finding in design["findings"]
    )
    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T5.1-WORKBENCH-STATIC",
        "kind": "tool_log",
        "runtime_level": "STATIC",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_workbench": "G:\\CODEX\\New Manga",
        "isolated_copy": str(WORKBENCH),
        "isolation": "copied src/docs/tests/config only; apps/test_assets/weights/verification excluded; original never modified",
        "git": {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8").stdout.strip(),
        },
        "file_count_copied": sum(1 for _ in WORKBENCH.rglob("*") if _.is_file()),
        "files_scanned": len(sources),
        "discovery": {
            "pages": len(discovery_report["pages"]),
            "capabilities": discovery_report["capabilities"],
            "unverified_paths": len(discovery_report["unverified_paths"]),
            "source_status": {item["source"]: item["status"] for item in discovery_report["sources"]},
        },
        "style_linter": {"summary": style["summary"], "by_rule": dict(style_rules)},
        "design_system": {"summary": design["summary"], "by_rule_or_dimension": dict(design_rules)},
        "generator_sha256": sha256_file(Path(__file__)),
        "limitations": [
            "Read-only static baseline; the application was not launched (apps/ excluded, 13GB tree).",
            "No import/browse/edit/save/export/undo execution; before/after interaction measurement not performed.",
            "Findings are SIMULATED/static and not a substitute for native probes.",
        ],
    }
    out = OUT_DIR / "workbench-static-baseline.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "evidence": str(out.relative_to(REPO_ROOT)), "pages": evidence["discovery"]["pages"], "style_findings": len(style["findings"]), "design_findings": len(design["findings"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
