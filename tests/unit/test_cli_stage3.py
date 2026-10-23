from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT

ENV = {"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "uiux_engine.cli", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **ENV},
    )


def test_modify_cli_dry_run_apply_revert(tmp_path: Path):
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    target = root / "src" / "app.tsx"
    target.write_text("export const App = 1;\n", encoding="utf-8")
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    plan = {
        "schema_version": "1.3.3",
        "plan_id": "P1",
        "task_id": "T3.1",
        "created_at": "2026-10-24T00:00:00+00:00",
        "write_scope": ["src/"],
        "changes": [{"path": "src/app.tsx", "action": "modify", "sha256_before": before, "content": "changed\n"}],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    dry = run_cli("modify", "--root", str(root), "--plan", str(plan_path))
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert target.read_text(encoding="utf-8") == "export const App = 1;\n"
    applied = run_cli("modify", "--root", str(root), "--plan", str(plan_path), "--apply", "--backup", str(tmp_path / "backup"))
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert target.read_text(encoding="utf-8") == "changed\n"
    reverted = run_cli("modify", "--root", str(root), "--plan", str(plan_path), "--revert", str(tmp_path / "backup"))
    assert reverted.returncode == 0
    assert target.read_text(encoding="utf-8") == "export const App = 1;\n"


def test_safety_cli_classifies_delete_as_p3(tmp_path: Path):
    plan = {"changes": [{"path": "src/a.ts", "action": "delete"}]}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    proc = run_cli("safety", "--plan", str(path))
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["level"] == "P3_DESTRUCTIVE_OR_USER_DATA"


def test_integrity_cli_verifies_chain(tmp_path: Path):
    from uiux_engine import integrity

    chain = integrity.build_chain([{"probe_id": "P1", "exit_code": 0}])
    chain_path = tmp_path / "chain.json"
    chain_path.write_text(json.dumps(chain), encoding="utf-8")
    proc = run_cli("integrity", "--chain", str(chain_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"] is True


def test_compat_cli_reports_degradation(tmp_path: Path):
    proc = run_cli("compat", "--agents-home", str(tmp_path))
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert any(check["id"] == "python" for check in payload["checks"])


def test_vault_cli_rejects_missing_manifest(tmp_path: Path):
    proc = run_cli("vault", "--root", str(tmp_path), "--manifest", str(tmp_path / "missing.json"))
    assert proc.returncode == 10
