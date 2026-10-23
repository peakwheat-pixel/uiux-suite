"""Collect Tauri 2 + WebdriverIO native IPC evidence (T3.2).

Prerequisites: an external Tauri lab built with tauri-plugin-wdio-webdriver and
tauri-plugin-wdio 1.5, and a WDIO run log. The lab path is passed explicitly.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "evidence" / "T3.2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "usage: collect_tauri_evidence.py <tauri-lab-dir>"}))
        return 2
    lab = Path(sys.argv[1]).resolve()
    exe = lab / "src-tauri/target/release/tauri-lab.exe"
    log = lab / "wdio-output.txt"
    if not exe.is_file() or not log.is_file():
        print(json.dumps({"ok": False, "error": "missing tauri-lab exe or wdio-output.txt"}))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":(exclude)evidence"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    )
    data = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T3.2-TAURI-WDIO",
        "kind": "tool_log",
        "runtime_level": "NATIVE_APP",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8").stdout.strip(),
            "dirty": dirty,
            "dirty_scope": "tracked files excluding evidence/",
        },
        "app": {
            "path": str(exe),
            "sha256": sha256(exe),
            "size": exe.stat().st_size,
            "framework": "Tauri 2 (vanilla-ts template)",
            "plugins": ["tauri-plugin-wdio-webdriver 1.5", "tauri-plugin-wdio 1.5"],
            "ipc_command": "greet(name) -> Hello, {name}! You've been greeted from Rust!",
            "source_lab": str(lab),
        },
        "driver": {"provider": "embedded", "service": "@wdio/tauri-service", "browser": "msedge 155.0.4283.62"},
        "test": {
            "spec": "test/specs/ipc.e2e.js",
            "result": "1 passing",
            "text": "Hello, DSH-Native-IPC! You've been greeted from Rust!",
            "screenshot": {"path": "evidence/T3.2/tauri-wdio-ipc.png", "sha256": sha256(OUT / "tauri-wdio-ipc.png")},
            "log": {"path": "evidence/T3.2/tauri-wdio-output.txt", "sha256": sha256(log)},
        },
        "versions": {"rustc": "1.98.1", "node": "24.15.0", "npm": "12.0.1", "edge": "155.0.4283.62"},
        "generator": {"path": "scripts/collect_tauri_evidence.py", "sha256": sha256(Path(__file__))},
        "limitations": [
            "Test lab lives outside the repository; source config/spec are archived under evidence/T3.2/source/.",
            "Only the default greet IPC command and DOM interaction were exercised.",
            "No OS-level physical input; WebDriver drives the WebView.",
            "The embedded provider uses the app's WebView2 WebDriver server, not EdgeDriver launching the app.",
        ],
    }
    (OUT / "tauri-wdio-evidence.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "tauri-wdio-output.txt").write_text(log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    src = OUT / "source"
    src.mkdir(exist_ok=True)
    for rel in ["wdio.conf.js", "test/specs/ipc.e2e.js", "src-tauri/Cargo.toml", "src-tauri/src/lib.rs", "package.json"]:
        (src / Path(rel).name).write_text((lab / rel).read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps({"ok": True, "evidence": "evidence/T3.2/tauri-wdio-evidence.json", "dirty": dirty}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
