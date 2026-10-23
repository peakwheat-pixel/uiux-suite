"""Collect T0.5 offline-install evidence from dist/wheels.

It builds a temporary venv, installs requirements with --no-index, then runs a
minimal engine command. Wheels themselves stay in gitignored dist/; this
evidence records their names and SHA-256 so a distributed package can be
verified. The generation script hash is included.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "evidence" / "T0.5"
WHEELS = REPO_ROOT / "dist" / "wheels"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        command,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _dirty_excluding_evidence() -> bool:
    status = run(["git", "status", "--porcelain"]).stdout
    for line in status.splitlines():
        path = line[3:].strip() if len(line) > 3 else ""
        if path and not path.startswith("evidence/"):
            return True
    return False


def main() -> int:
    wheels = sorted(WHEELS.glob("*.whl"))
    if not wheels:
        print(json.dumps({"ok": False, "error": f"no wheels in {WHEELS}"}, ensure_ascii=False))
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        venv = Path(temp_dir) / "venv"
        create = run([sys.executable, "-m", "venv", str(venv)])
        python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
        install = run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(WHEELS),
                "-r",
                str(REPO_ROOT / "requirements.txt"),
            ]
        )
        if install.returncode == 0:
            smoke = run(
                [str(python), "-m", "uiux_engine.cli", "enums"],
                cwd=REPO_ROOT,
                extra_env={"PYTHONPATH": str(REPO_ROOT / "runtime")},
            )
        else:
            smoke = subprocess.CompletedProcess([], 1, "", "skipped: install failed")
        log = (
            "=== python -m venv ===\n"
            + create.stdout
            + create.stderr
            + "\n=== pip install --no-index ===\n"
            + install.stdout
            + install.stderr
            + "\n=== uiux_engine.cli enums ===\n"
            + smoke.stdout[:2000]
            + smoke.stderr
        )
        log_path = OUT_DIR / "offline-install.txt"
        log_path.write_text(log, encoding="utf-8")

    evidence = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T0.5-OFFLINE-INSTALL",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": run(["git", "rev-parse", "HEAD"]).stdout.strip(),
            "dirty": _dirty_excluding_evidence(),
            "dirty_scope": "tracked files excluding evidence/ (collectors rewrite evidence)",
        },
        "wheels": [
            {
                "name": wheel.name,
                "size": wheel.stat().st_size,
                "sha256": sha256_file(wheel),
            }
            for wheel in wheels
        ],
        "commands": {
            "create_venv": create.args,
            "install": install.args,
            "smoke": smoke.args,
        },
        "exit_codes": {
            "create_venv": create.returncode,
            "install": install.returncode,
            "smoke": smoke.returncode,
        },
        "install_stdout_sha256": hashlib.sha256((install.stdout + install.stderr).encode("utf-8")).hexdigest(),
        "log_file": str(log_path.relative_to(REPO_ROOT)),
        "log_sha256": sha256_file(log_path),
        "generator_sha256": sha256_file(Path(__file__)),
        "requirements_sha256": sha256_file(REPO_ROOT / "requirements.txt"),
    }
    out = OUT_DIR / "offline-install-evidence.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = create.returncode == 0 and install.returncode == 0 and smoke.returncode == 0
    print(json.dumps({"ok": ok, "evidence": str(out.relative_to(REPO_ROOT)), "wheels": len(wheels)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
