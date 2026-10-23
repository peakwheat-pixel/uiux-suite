from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

pytest.importorskip("PySide6")


def test_workbench_end_to_end(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_workbench_e2e.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "runtime"),
            "PYTHONUTF8": "1",
            "UIUX_EVIDENCE_DIR": str(tmp_path / "evidence"),
        },
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    evidence = json.loads((tmp_path / "evidence" / "workbench-e2e-evidence.json").read_text(encoding="utf-8"))
    assert evidence["all_steps_ok"] is True
    assert evidence["runtime_level"] == "NATIVE_QT_APP"
    assert len(evidence["steps"]) == 9
    assert all(step["ok"] for step in evidence["steps"])
    before = evidence["before_after"]["before"]
    after = evidence["before_after"]["after"]
    assert after["font_px"] > before["font_px"]
    assert after["button_min"][1] > before["button_min"][1]
    assert after["contrast"] > before["contrast"]
    assert len(evidence["screenshots"]) == 2
    for shot in evidence["screenshots"]:
        assert Path(shot["path"]).is_file()
