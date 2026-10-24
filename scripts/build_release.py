"""Build and verify the Stage 5 release package (T5.5)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST = REPO_ROOT / "dist"
VERSION = "1.3.4"
RELEASE_VERSION = VERSION
SUITE_NAME = f"uiux-suite-{RELEASE_VERSION}"
ZIP_PATH = DIST / f"{SUITE_NAME}-win64.zip"
STAGING = DIST / SUITE_NAME
EVIDENCE = REPO_ROOT / "evidence" / "T5.5"

INCLUDE_DIRS = ["runtime", "contracts", "knowledge", "skills", "scripts", "docs", "qa", "sandbox", "fixtures", "inventory"]
INCLUDE_FILES = [
    "SPEC_V1.3.4.md",
    "SPEC_V1.3.3.md",
    "README.md",
    "FINAL_DELIVERY_REPORT.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.lock",
]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def role_for(path: str) -> str:
    if path.startswith("runtime/"):
        return "runtime"
    if path.startswith("contracts/"):
        return "schema"
    if path.startswith("skills/") and path.endswith("launch.py"):
        return "launcher"
    if path.startswith("skills/"):
        return "skill"
    if path.startswith("knowledge/"):
        return "knowledge"
    if path.startswith("docs/"):
        return "docs"
    if path in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        return "license"
    return "other"


def stage() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    for name in INCLUDE_DIRS:
        source = REPO_ROOT / name
        if source.is_dir():
            shutil.copytree(source, STAGING / name, ignore=IGNORE)
    for name in INCLUDE_FILES:
        source = REPO_ROOT / name
        if source.is_file():
            shutil.copy2(source, STAGING / name)
    wheels = REPO_ROOT / "dist" / "wheels"
    if wheels.is_dir():
        shutil.copytree(wheels, STAGING / "wheels", ignore=IGNORE)


def make_manifest() -> dict:
    files = []
    for path in sorted(STAGING.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(STAGING).as_posix()
        files.append({"path": rel, "sha256": sha256_file(path), "size": path.stat().st_size, "role": role_for(rel)})
    manifest = {
        "schema_version": VERSION,
        "suite_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "builder": "scripts/build_release.py",
        "target_platform": {
            "os": "windows-11",
            "python": sys.version.split()[0],
            "node": _node_version() or "unknown",
        },
        "normalization": {"path_separator": "/", "case_policy": "casefolded_windows", "eol_normalized": False},
        "files": files,
        "excluded_patterns": ["**/__pycache__/**", "**/*.pyc", ".venv/**", "tests/**", "evidence/**", "plan/**"],
        "include_launcher": True,
        "include_schemas": True,
        "include_licenses": True,
        "bundle_sha256": hashlib.sha256(
            json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    from uiux_engine import contracts

    errors = contracts.validation_errors("release-manifest", manifest)
    if errors:
        raise SystemExit("release manifest invalid: " + "; ".join(errors))
    (STAGING / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _node_version() -> str | None:
    exe = shutil.which("node")
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def zip_package() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(STAGING.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST).as_posix())
    (DIST / "SHA256SUMS.txt").write_text(
        f"{sha256_file(ZIP_PATH)}  {ZIP_PATH.name}\n"
        + "".join(
            f"{sha256_file(STAGING / item['path'])}  {SUITE_NAME}/{item['path']}\n"
            for item in json.loads((STAGING / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))["files"]
        ),
        encoding="utf-8",
    )


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def verify_package() -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    git_commit = _git("rev-parse", "HEAD")
    git_dirty = bool(_git("status", "--porcelain"))
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        extract = temp / "extract"
        with zipfile.ZipFile(ZIP_PATH) as archive:
            archive.extractall(extract)
        suite_root = extract / SUITE_NAME
        project = temp / "project"
        project.mkdir()
        agents = temp / "agents"
        env = dict(os.environ)
        env.update({"DSH_AGENTS_HOME": str(agents), "DSH_HOME": str(temp / "dsh"), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        install = subprocess.run(
            [
                sys.executable,
                str(suite_root / "scripts" / "setup_skill.py"),
                "--host",
                "generic",
                "install",
                "--scope",
                "project",
                "--project",
                str(project),
                "--source",
                str(suite_root),
                "--version",
                VERSION,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        launcher = project / ".agents" / "skills" / "uiux" / "scripts" / "launch.py"
        enums = subprocess.run([sys.executable, str(launcher), "enums"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        doctor = subprocess.run([sys.executable, str(launcher), "doctor", "--scope", "project", "--project", str(project)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        log = (
            "=== install ===\n"
            + install.stdout
            + install.stderr
            + "\n=== enums ===\n"
            + enums.stdout[:1000]
            + enums.stderr
            + "\n=== doctor ===\n"
            + doctor.stdout[:3000]
            + doctor.stderr
        )
        (EVIDENCE / "release-install.txt").write_text(log, encoding="utf-8")
        result = {
            "ok": install.returncode == 0 and enums.returncode == 0 and doctor.returncode == 0,
            "zip": str(ZIP_PATH.relative_to(REPO_ROOT)),
            "zip_sha256": sha256_file(ZIP_PATH),
            "zip_size": ZIP_PATH.stat().st_size,
            "manifest_sha256": sha256_file(suite_root / "RELEASE_MANIFEST.json"),
            "git": {"commit": git_commit, "dirty": git_dirty},
            "bit_reproducible": False,
            "reproducibility_note": "manifest generated_at and target_platform make byte-identical rebuilds non-deterministic; verify by recorded ZIP SHA256",
            "install_exit": install.returncode,
            "enums_exit": enums.returncode,
            "doctor_exit": doctor.returncode,
            "log": str((EVIDENCE / "release-install.txt").relative_to(REPO_ROOT)),
            "log_sha256": sha256_file(EVIDENCE / "release-install.txt"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (EVIDENCE / "release-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="", help="release label for the package name, e.g. rc1")
    args = parser.parse_args(argv)
    global RELEASE_VERSION, SUITE_NAME, ZIP_PATH, STAGING
    # the contract version stays strict semver (1.3.4); a label only marks the
    # package/artifact as a release candidate
    RELEASE_VERSION = VERSION
    suffix = f"-{args.label}" if args.label else ""
    SUITE_NAME = f"uiux-suite-{VERSION}{suffix}"
    ZIP_PATH = DIST / f"{SUITE_NAME}-win64.zip"
    STAGING = DIST / SUITE_NAME
    DIST.mkdir(exist_ok=True)
    stage()
    manifest = make_manifest()
    zip_package()
    result = verify_package()
    print(json.dumps({"ok": result["ok"], "files": len(manifest["files"]), **result}, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
