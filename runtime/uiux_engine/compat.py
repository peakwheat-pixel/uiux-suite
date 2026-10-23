"""Host compatibility matrix and degradation paths (T4.1/T4.2/T4.4)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HOSTS = {"dsh", "codex", "claude-code", "zcode", "antigravity", "qoder", "generic"}


def host_matrix(observed_host: str = "dsh", evidence_ref: str | None = None) -> dict[str, Any]:
    rows = []
    for host in sorted(HOSTS):
        if host == observed_host and evidence_ref:
            rows.append({"host": host, "status": "OBSERVED", "evidence_refs": [evidence_ref]})
        else:
            rows.append(
                {
                    "host": host,
                    "status": "UNVERIFIED",
                    "reason_code": "HOST_UNVERIFIED",
                    "detail": "no host-specific execution evidence; do not claim compatibility",
                }
            )
    return {
        "observed_host": observed_host,
        "hosts": rows,
        "verified_count": sum(1 for row in rows if row["status"] == "OBSERVED"),
        "unverified_count": sum(1 for row in rows if row["status"] == "UNVERIFIED"),
    }


def _node_version() -> str | None:
    exe = shutil.which("node")
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def degradation_report(agents_home: str | Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append({"id": "python", "ok": sys.version_info >= (3, 10), "detail": sys.version.split()[0], "reason_code": None if sys.version_info >= (3, 10) else "PYTHON_EXE_MISSING"})
    node = _node_version()
    checks.append({"id": "node", "ok": node is not None, "detail": node or "missing", "reason_code": None if node else "HOST_UNVERIFIED"})
    gui = platform.system() == "Windows" or bool(os.environ.get("DISPLAY"))
    checks.append({"id": "gui", "ok": gui, "detail": platform.platform(), "reason_code": None if gui else "HOST_UNVERIFIED"})
    if agents_home:
        root = Path(agents_home)
        for skill in ("uiux", "uiux-verify"):
            link = root / "skills" / skill / "suite-link.json"
            checks.append({"id": f"link-{skill}", "ok": link.is_file(), "detail": str(link), "reason_code": None if link.is_file() else "LINK_MISSING"})
    else:
        checks.append({"id": "offline-mode", "ok": True, "detail": "no network required for local detectors", "reason_code": None})
    return {"ok": all(check["ok"] for check in checks), "checks": checks}
