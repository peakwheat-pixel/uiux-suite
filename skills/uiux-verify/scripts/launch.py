#!/usr/bin/env python3
"""Thin launcher for the `uiux` skill.

It locates the versioned suite through `<skill_root>/suite-link.json`, verifies
the release manifest, then delegates to `uiux_engine.cli`.

Stable failure codes (documented in docs/CLI.md):
  3 LINK_MISSING / LINK_INVALID
  4 RELEASE_ROOT_MISSING / VERSION_MISMATCH
  5 PYTHON_EXE_MISSING
  6 MANIFEST_MISMATCH
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def emit(code: int, reason: str, detail: str = "") -> int:
    print(json.dumps({"ok": False, "code": reason, "detail": detail}, ensure_ascii=False))
    return code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_suite_root(skill_root: Path, link: dict) -> Path:
    raw = Path(link["suite_root"])
    if link["path_kind"] == "relative_to_skill_root":
        return (skill_root / raw).resolve()
    return raw.resolve()


def verify_manifest(suite_root: Path, manifest_path: Path, expected_version: str) -> str | None:
    if not manifest_path.is_file():
        return "MANIFEST_CORRUPT"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "MANIFEST_CORRUPT"
    if manifest.get("suite_version") != expected_version:
        return "VERSION_MISMATCH"
    for entry in manifest.get("files", []):
        target = suite_root / entry["path"]
        if not target.is_file():
            return "MANIFEST_MISMATCH"
        if sha256_file(target) != entry["sha256"]:
            return "MANIFEST_MISMATCH"
    return None


def python_usable(exe: str | Path) -> bool:
    path = Path(exe)
    if not path.is_file():
        return False
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [str(path), "-c", "import jsonschema"],
            capture_output=True,
            env=env,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def resolve_python(link: dict) -> str | None:
    candidates: list[str] = []
    if link.get("python_exe"):
        candidates.append(str(link["python_exe"]))
    candidates.append(sys.executable)
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if python_usable(normalized):
            return normalized
    return None


def main(argv: list[str]) -> int:
    skill_root = Path(__file__).resolve().parent.parent
    link_path = skill_root / "suite-link.json"
    if not link_path.is_file():
        return emit(3, "LINK_MISSING", str(link_path))
    try:
        link = json.loads(link_path.read_text(encoding="utf-8"))
        for key in ("schema_version", "suite_id", "active_version", "path_kind", "suite_root", "manifest_relpath"):
            if key not in link:
                raise KeyError(key)
    except (OSError, ValueError, KeyError) as exc:
        return emit(3, "LINK_INVALID", f"{link_path}: {exc}")

    suite_root = resolve_suite_root(skill_root, link)
    if not suite_root.is_dir():
        return emit(4, "RELEASE_ROOT_MISSING", str(suite_root))

    problem = verify_manifest(suite_root, suite_root / link["manifest_relpath"], link["active_version"])
    if problem:
        return emit(6, problem, str(suite_root / link["manifest_relpath"]))

    python_exe = resolve_python(link)
    if python_exe is None:
        return emit(5, "PYTHON_EXE_MISSING", "no Python with jsonschema found (suite-link, sys.executable, PATH)")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(suite_root / "runtime")
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    if argv and argv[0] == "doctor":
        installed_doctor = suite_root / "setup_skill.py"
        if not installed_doctor.is_file():
            return emit(7, "INSTALLED_DOCTOR_MISSING", str(installed_doctor))
        completed = subprocess.run(
            [python_exe, str(installed_doctor), "doctor", *argv[1:]],
            cwd=str(suite_root),
            env=env,
        )
        return completed.returncode

    completed = subprocess.run(
        [python_exe, "-m", "uiux_engine.cli", *argv],
        cwd=str(suite_root),
        env=env,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
