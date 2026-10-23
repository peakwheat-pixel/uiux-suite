"""Measure detector/build latency against the documented budget (m8)."""
from __future__ import annotations

import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "runtime"))

BUDGETS_MS = {"style_10_files": 3000, "token_compile_css": 300, "discovery_small": 8000}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timeit(func, repeats: int = 3) -> float:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        func()
        samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 2)


def main() -> int:
    from uiux_engine import design_system, discovery, style_linter, token_compiler

    candidates = []
    for base in (REPO_ROOT / "tests" / "fixtures" / "ground_truth", REPO_ROOT / "tests" / "fixtures" / "contracts" / "valid"):
        candidates.extend(sorted(base.rglob("*")))
    style_files = [
        path for path in candidates
        if path.suffix.lower() in {".tsx", ".jsx", ".css", ".qss"}
    ][:10]

    def style_run() -> None:
        style_linter.lint_files(style_files, root=REPO_ROOT)
        design_system.token_index()

    def token_run() -> None:
        token_compiler.to_css()

    discovery_root = Path(os.environ.get("UIUX_DISCOVERY_ROOT", str(REPO_ROOT / "sandbox" / "workbench_app")))

    def discovery_run() -> None:
        discovery.discover(discovery_root)

    timings = {
        "style_10_files": timeit(style_run),
        "token_compile_css": timeit(token_run),
        "discovery_small": timeit(discovery_run),
    }
    over = {name: value for name, value in timings.items() if value > BUDGETS_MS[name]}
    report = {
        "schema_version": "1.3.3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timings_ms": timings,
        "budgets_ms": BUDGETS_MS,
        "over_budget": over,
        "ok": not over,
        "generator": {"path": "scripts/measure_performance.py", "sha256": sha256(Path(__file__))},
        "limitations": ["Small sample on developer machine; not a large-project benchmark."],
    }
    out = REPO_ROOT / "evidence" / "T1.0" / "performance-budget.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "timings": timings, "over": over}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
