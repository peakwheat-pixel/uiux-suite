"""TASK-04 orchestration: isolated write execution with backup/restore proof.

Runs probe_v135c.mjs (settings save + synthetic book creation + disabled-delete
attempt + recycle-bin surface) inside the sandbox, then restores the sandbox and
verifies byte-level consistency.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parents[2]
ROOT = Path(r"G:\AI\uiux-v135")
SANDBOX_ALLOWED = ROOT / "sandbox"
SANDBOX_RUN = ROOT / "sandbox" / "audit" / "run-pilot"
BACKUP_DIR = ROOT / "sandbox" / "backups" / "task04"
PILOT = ROOT / "tools" / "pilot"
OUT = ROOT / "evidence" / "task04"
PROBE_RUN = "pilot-run-v135c"

sys.path.insert(0, str(SUITE / "runtime"))
from uiux_engine import isolated_exec  # noqa: E402


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "M2RC1_PACKAGED": "1", "PYTHONUTF8": "1"}

    def executor(sandbox: Path) -> dict:
        proc = subprocess.run(
            ["node", "probe_v135c.mjs", PROBE_RUN, "run-pilot"],
            cwd=str(PILOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env, timeout=600,
        )
        run_log = ROOT / "evidence" / "audit" / "probe" / PROBE_RUN / "run-log.json"
        log = json.loads(run_log.read_text(encoding="utf-8")) if run_log.is_file() else {}
        return {
            "node_exit": proc.returncode,
            "stdout_tail": proc.stdout[-500:],
            "stderr_tail": proc.stderr[-500:],
            "captures": [c["name"] for c in log.get("captures", [])],
            "errors": log.get("errors", []),
            "steps": [s.get("name") for s in log.get("steps", [])],
        }

    record = isolated_exec.run_isolated(
        action_id="TASK04-ISOLATED-WRITES",
        root=SANDBOX_RUN,
        allowed_root=SANDBOX_ALLOWED,
        backup_dir=BACKUP_DIR,
        executor=executor,
    )
    record["probe_run"] = PROBE_RUN
    record["evidence_run_log"] = str(ROOT / "evidence" / "audit" / "probe" / PROBE_RUN / "run-log.json")
    (OUT / "isolated-execution.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    captures = record.get("result", {}).get("captures", [])
    write_checks = {
        "settings_write_executed": any("settings write" == s for s in record.get("result", {}).get("steps", [])),
        "create_book_executed": any("create book" == s for s in record.get("result", {}).get("steps", [])),
        "delete_entry_attempted": any("delete entry attempt" == s for s in record.get("result", {}).get("steps", [])),
        "recycle_bin_inspected": any("recycle bin" == s for s in record.get("result", {}).get("steps", [])),
    }
    summary = {
        "verdict": record["verdict"],
        "state": record["state"],
        "backup_files": record.get("backup", {}).get("files"),
        "backup_manifest_sha256": record.get("backup", {}).get("manifest_sha256"),
        "restore_consistent": record.get("restore_consistent"),
        "captures": len(captures),
        "write_checks": write_checks,
        "errors": record.get("errors"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
