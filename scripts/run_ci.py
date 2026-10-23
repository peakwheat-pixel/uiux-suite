"""Local CI runner for Windows (M10).

Runs the deterministic suites in order and records a machine-readable summary.
It is not a GitHub/gitea runner; real runner execution remains UNVERIFIED.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
OUT = REPO_ROOT / "evidence" / "T1.0" / "ci-local.json"

STEPS = [
    ("pytest", [str(PYTHON), "-m", "pytest", "tests", "-q"]),
    ("attacks", [str(PYTHON), "scripts/run_attack_suite.py"]),
    ("stage1", [str(PYTHON), "scripts/run_stage1_suite.py"]),
    ("qt-qpa", [str(PYTHON), "scripts/collect_qt_evidence.py"]),
    ("workbench-e2e", [str(PYTHON), "scripts/run_workbench_e2e.py"]),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    import os

    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1"}
    started = time.perf_counter()
    runs = []
    for name, command in STEPS:
        step_started = time.perf_counter()
        proc = subprocess.run(command, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        runs.append(
            {
                "step": name,
                "exit_code": proc.returncode,
                "ms": round((time.perf_counter() - step_started) * 1000, 2),
                "stdout_tail": proc.stdout[-600:],
                "stderr_tail": proc.stderr[-600:],
            }
        )
    report = {
        "schema_version": "1.3.3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8").stdout.strip(),
            "dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8").stdout.strip()),
        },
        "runs": runs,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "ok": all(run["exit_code"] == 0 for run in runs),
        "generator": {"path": "scripts/run_ci.py", "sha256": sha256(Path(__file__))},
        "limitations": [
            "Local Windows run only; no GitHub/gitea hosted runner was used.",
            "Artifacts are the existing evidence files, not CI service artifacts.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "runs": [(run["step"], run["exit_code"]) for run in runs], "duration_ms": report["duration_ms"]}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
