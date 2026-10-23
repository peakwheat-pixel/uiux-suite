from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

pytest.importorskip("PySide6")

from uiux_engine import qt_probe


def test_native_qpa_measurement(tmp_path: Path):
    shot = tmp_path / "native.png"
    result = qt_probe.measure(str(shot))
    assert result["ok"] is True
    assert result["platform"] == "windows"
    assert result["runtime_level"] == "NATIVE_QPA"
    assert result["screen"]["device_pixel_ratio"] == 1.0
    assert result["fonts"]["cjk_yahei"] is True
    assert result["focus"]["edit_focusable"] is True
    assert shot.is_file()
    assert result["screenshot"]["sha256"] == __import__("hashlib").sha256(shot.read_bytes()).hexdigest()


def test_scale_factors_change_device_pixel_ratio(tmp_path: Path):
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(REPO_ROOT / "runtime"), "PYTHONUTF8": "1", "QT_QPA_PLATFORM": "windows"})
    sizes = {}
    for scale in ("1.0", "1.25", "1.5"):
        env["QT_SCALE_FACTOR"] = scale
        shot = tmp_path / f"scale-{scale}.png"
        proc = subprocess.run(
            [sys.executable, "-m", "uiux_engine.qt_probe", "--screenshot", str(shot)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["screen"]["device_pixel_ratio"] == float(scale)
        sizes[scale] = payload["screenshot"]["size"][0]
    assert sizes["1.0"] < sizes["1.25"] < sizes["1.5"]


def test_scale_sweep_is_deterministic(tmp_path: Path):
    first = qt_probe.measure(str(tmp_path / "a.png"))["screen"]
    second = qt_probe.measure(str(tmp_path / "b.png"))["screen"]
    assert first == second
