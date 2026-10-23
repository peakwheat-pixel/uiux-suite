"""Check command consistency in docs (M16)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = [REPO / "README.md", REPO / "docs" / "INSTALL.md", REPO / "docs" / "CLI.md"]
PATTERNS = [
    (re.compile(r"(?<!\.venv\\Scripts\\)python\s+-m\s+uiux_engine"), "bare python -m uiux_engine (missing venv path)"),
    (re.compile(r"python\s+scripts\\setup_skill\.py", re.IGNORECASE), "bare python setup_skill (missing venv path)"),
    (re.compile(r"python\s+skills\\uiux\\scripts\\launch\.py", re.IGNORECASE), "bare python launch.py (acceptable only if documented launcher)"),
]
REQUIRED = ["scripts/setup_skill.py", "skills/uiux/scripts/launch.py", "skills/uiux-verify/scripts/launch.py"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    issues = []
    files = []
    for path in DOCS:
        if not path.is_file():
            issues.append({"file": str(path), "issue": "missing documentation file"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        files.append({"path": str(path.relative_to(REPO)), "sha256": sha256(path)})
        for line_number, line in enumerate(text.splitlines(), 1):
            for pattern, label in PATTERNS:
                if pattern.search(line):
                    issues.append({"file": str(path.relative_to(REPO)), "line": line_number, "issue": label, "text": line.strip()[:160]})
    missing_scripts = [rel for rel in REQUIRED if not (REPO / rel).is_file()]
    for rel in missing_scripts:
        issues.append({"file": rel, "issue": "required script missing"})
    report = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-M16-COMMAND-CONSISTENCY",
        "kind": "tool_log",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "checks": ["venv interpreter in install commands", "setup_skill/launch paths exist", "no bare uiux_engine module invocation"],
        "issues": issues,
        "ok": not issues,
        "generator": {"path": "scripts/check_command_consistency.py", "sha256": sha256(Path(__file__))},
        "limitations": ["Static documentation check only; does not execute every command."],
    }
    out = REPO / "evidence" / "T1.0" / "command-consistency.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "issues": issues[:5]}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
