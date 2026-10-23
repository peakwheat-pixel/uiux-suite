"""Collect PySide6 QPA/DPI evidence (T3.3)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "evidence" / "T3.3"
PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
SCALES = ("1.0", "1.25", "1.5")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_scale(scale: str) -> dict:
    screenshot = OUT_DIR / f"qt-scale-{scale}.png"
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT / "runtime"),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "QT_QPA_PLATFORM": "windows",
            "QT_SCALE_FACTOR": scale,
        }
    )
    proc = subprocess.run(
        [str(PYTHON), "-m", "uiux_engine.qt_probe", "--screenshot", str(screenshot)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result = {"ok": False, "error": "invalid json", "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    result["exit_code"] = proc.returncode
    result["stderr_tail"] = proc.stderr[-500:]
    return result


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = {scale: run_scale(scale) for scale in SCALES}
    ok = all(run.get("ok") for run in runs.values())
    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T3.3-QPA",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8"
            ).stdout.strip(),
            "dirty": bool(
                subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8").stdout.strip()
            ),
        },
        "python": sys.version.split()[0],
        "runs": runs,
        "ok": ok,
        "generator_sha256": sha256_file(Path(__file__)),
        "limitations": [
            "100% is the current monitor's native QPA measurement; 125%/150% are simulated with QT_SCALE_FACTOR, not a physical monitor DPI change.",
            "No click-through or focus traversal; widget focus policies are read, not exercised.",
            "No visual-regression baseline beyond the captured PNG hashes.",
        ],
    }
    out = OUT_DIR / "qt-qpa-evidence.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "evidence": str(out.relative_to(REPO_ROOT)), "scales": list(runs)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
