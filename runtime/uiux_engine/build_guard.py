"""Untrusted-project build/command execution guard (M8).

Only known test/build tools are allowed; destructive, network and
out-of-root operations are denied unless explicitly permitted.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any

ALLOWED_EXECUTABLES = {
    "pytest",
    "python",
    "python3",
    "cargo",
    "rustc",
    "npm",
    "node",
    "npx",
    "ruff",
    "mypy",
    "dotnet",
    "msbuild",
}
DESTRUCTIVE = ("rm", "del", "erase", "rmdir", "format", "shutdown", "taskkill", "reg")
NETWORK = ("curl", "wget", "invoke-webrequest", "iwr", "git")
DANGEROUS_ARGS = ("--force", "-rf", "/f", "/s", "push", "publish", "install")


def check(command: str | list[str], root: str | Path, *, allow_network: bool = False) -> dict[str, Any]:
    parts = shlex.split(command, posix=os.name != "nt") if isinstance(command, str) else [str(part) for part in command]
    reasons: list[str] = []
    if not parts:
        return {"decision": "DENY", "reasons": ["EMPTY_COMMAND"], "parts": []}
    executable = Path(parts[0]).name.lower()
    if executable not in ALLOWED_EXECUTABLES:
        reasons.append(f"EXECUTABLE_NOT_ALLOWED:{executable}")
    root_path = Path(root).resolve()
    for part in parts:
        if part.startswith("-") or part in DANGEROUS_ARGS:
            continue
        candidate = Path(part)
        if candidate.is_absolute():
            try:
                candidate.resolve().relative_to(root_path)
            except ValueError:
                reasons.append(f"PATH_OUTSIDE_ROOT:{part}")
    lowered = executable.lower()
    if lowered in DESTRUCTIVE or any(part.lower() in DESTRUCTIVE for part in parts[1:3]):
        reasons.append("DESTRUCTIVE_COMMAND")
    if not allow_network and (lowered in NETWORK or lowered in {"npx"}):
        reasons.append("NETWORK_REQUIRES_EXPLICIT_FLAG")
    return {
        "decision": "ALLOW" if not reasons else "DENY",
        "reasons": reasons,
        "parts": parts,
        "allow_network": allow_network,
    }
