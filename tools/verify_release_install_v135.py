"""Independent clean-install verification for any V1.3.4 package.

Usage:
  python verify_release_install.py --package <zip> --version 1.3.4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ACC = Path(r"G:\\AI\\uiux-v135")
PACKAGES = ACC / "packages"
SANDBOX = ACC / "sandbox" / "release-install"
EVIDENCE = ACC / "evidence" / "release"
PYTHON = sys.executable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv: list[str], env: dict[str, str]) -> dict:
    proc = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=900,
    )
    return {"argv": [str(item) for item in argv], "exit_code": proc.returncode,
            "stdout": proc.stdout[-5000:], "stderr": proc.stderr[-2000:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", default="1.3.4")
    parser.add_argument("--sums")
    args = parser.parse_args()
    zip_path = Path(args.package)
    sums_path = Path(args.sums) if args.sums else PACKAGES / f"uiux-suite-{args.version}-SHA256SUMS.txt"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True)

    sums: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            sums[name.strip()] = digest
    zip_digest = sha256_file(zip_path)
    sums_ok = sums.get(zip_path.name) == zip_digest

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(SANDBOX / "extract")
    tops = [p for p in (SANDBOX / "extract").iterdir() if p.is_dir()]
    suite_root = tops[0]
    manifest = json.loads((suite_root / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    manifest_mismatch = [
        entry["path"] for entry in manifest["files"]
        if not (suite_root / entry["path"]).is_file() or sha256_file(suite_root / entry["path"]) != entry["sha256"]
    ]
    forbidden = [
        path.relative_to(suite_root).as_posix()
        for pattern in ("evidence", "tests", ".uiux", "dist")
        for path in suite_root.rglob(pattern)
    ]

    project = SANDBOX / "project"
    agents = SANDBOX / "agents"
    dsh_home = SANDBOX / "dsh"
    project.mkdir()
    env = dict(os.environ)
    env.update({
        "DSH_AGENTS_HOME": str(agents), "DSH_HOME": str(dsh_home),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
        "PYTHONPATH": str(suite_root / "runtime"),
    })
    install = run([PYTHON, str(suite_root / "scripts" / "setup_skill.py"), "--host", "generic",
                   "install", "--scope", "project", "--project", str(project),
                   "--source", str(suite_root), "--version", args.version], env)
    link_path = project / ".agents" / "skills" / "uiux" / "suite-link.json"
    link = json.loads(link_path.read_text(encoding="utf-8")) if link_path.is_file() else {}
    launcher = project / ".agents" / "skills" / "uiux" / "scripts" / "launch.py"
    vlauncher = project / ".agents" / "skills" / "uiux-verify" / "scripts" / "launch.py"
    enums = run([PYTHON, str(launcher), "enums"], env)
    venums = run([PYTHON, str(vlauncher), "enums"], env)
    doctor = run([PYTHON, str(launcher), "doctor", "--scope", "project", "--project", str(project)], env)
    again = run([PYTHON, str(launcher), "enums"], env)

    def parse(proc: dict) -> dict:
        try:
            return json.loads(proc["stdout"])
        except ValueError:
            return {}

    doctor_payload = parse(doctor)
    enums_payload = parse(enums)
    venums_payload = parse(venums)
    result = {
        "schema_version": "1.3.4",
        "kind": "release_install_verification",
        "package": {
            "name": zip_path.name, "sha256": zip_digest, "size": zip_path.stat().st_size,
            "sha256sums_match": sums_ok, "files": len(manifest["files"]),
            "suite_version": manifest["suite_version"],
        },
        "extract": {
            "suite_root": str(suite_root),
            "manifest_file_mismatch": manifest_mismatch,
            "forbidden_payload": forbidden,
        },
        "install": {
            "exit": install["exit_code"], "active_version": link.get("active_version"),
            "schema_version": link.get("schema_version"), "version_arg": args.version,
        },
        "entrypoints": {
            "uiux_enums_exit": enums["exit_code"],
            "uiux_enums_schema_version": enums_payload.get("schema_version"),
            "verify_enums_exit": venums["exit_code"],
            "verify_enums_schema_version": venums_payload.get("schema_version"),
            "identical_enum_dictionaries": enums_payload == venums_payload,
            "fresh_process_enums_exit": again["exit_code"],
        },
        "doctor": {
            "exit": doctor["exit_code"], "overall_status": doctor_payload.get("overall_status"),
            "ok": doctor_payload.get("ok"),
            "checks": [{"name": c.get("name"), "status": c.get("status"), "detail": c.get("detail")}
                       for c in doctor_payload.get("checks", [])],
        },
        "logs": {"install_tail": install["stdout"][-1000:], "doctor_tail": doctor["stdout"][:2000]},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    result["ok"] = (
        sums_ok and not manifest_mismatch and not forbidden
        and install["exit_code"] == 0
        and enums["exit_code"] == 0 and venums["exit_code"] == 0
        and doctor["exit_code"] == 0 and again["exit_code"] == 0
        and link.get("active_version") == args.version
    )
    out = EVIDENCE / "release-install-verification.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": result["ok"], "sha256sums_match": sums_ok,
        "manifest_mismatch": len(manifest_mismatch), "forbidden": forbidden,
        "install_exit": install["exit_code"], "enums_exit": enums["exit_code"],
        "doctor_exit": doctor["exit_code"], "doctor_status": doctor_payload.get("overall_status"),
        "evidence": str(out),
    }, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

