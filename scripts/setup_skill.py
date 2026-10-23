"""Install / doctor / repair for the Universal UI/UX Engineering suite (V1.3.3).

Commands:
    python scripts/setup_skill.py install --scope user --host dsh
    python scripts/setup_skill.py install --scope project --project "G:/demo" --host generic
    python scripts/setup_skill.py doctor --scope user [--project G:/demo]
    python scripts/setup_skill.py repair --scope user --version 1.3.3

Design rules:
- The suite is installed under <agents_home>/uiux-suite/versions/<version>/.
- Each skill entry holds SKILL.md, references/, scripts/launch.py and suite-link.json.
- Unknown existing skill directories are never overwritten.
- Every installed file is registered in state/install-<version>.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from uiux_engine import contracts  # noqa: E402

SUITE_ID = "universal-uiux-engineering"
SKILLS = ("uiux", "uiux-verify")
DEFAULT_VERSION = "1.3.3"
SCHEMA_VERSION = "1.3.3"
MANIFEST_NAME = "RELEASE_MANIFEST.json"
EXCLUDE = {"__pycache__", ".pytest_cache", ".venv"}


def python_works(candidate: str | Path) -> bool:
    path = Path(candidate)
    if not path.is_file():
        return False
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [
                str(path),
                "-c",
                "import sys, importlib.metadata as m; v=m.version('jsonschema').split('.'); "
                "sys.exit(0 if sys.version_info >= (3, 10) and v[0] == '4' and int(v[1]) >= 20 else 3)",
            ],
            capture_output=True,
            env=env,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def python_version_of(exe: str | Path | None) -> str | None:
    if not exe or not Path(exe).is_file():
        return None
    try:
        proc = subprocess.run(
            [str(exe), "-c", "import sys; print(sys.version.split()[0])"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def dependency_version_of(exe: str | Path | None, package: str) -> str | None:
    if not exe or not Path(exe).is_file():
        return None
    try:
        proc = subprocess.run(
            [str(exe), "-c", f"import importlib.metadata as m; print(m.version({package!r}))"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def select_python_exe(explicit: str | None = None) -> str | None:
    """Choose a Python that satisfies the suite runtime (>=3.10, jsonschema 4.20–4.x)."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    candidates.append(sys.executable)
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if python_works(candidate):
            return normalized
    return None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit(source: Path) -> str | None:
    if not (source / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(source),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def resolve_agents_home(scope: str, project: str | None) -> Path:
    if scope == "project":
        if not project:
            raise SystemExit("--project is required for --scope project")
        return Path(project).resolve() / ".agents"
    override = os.environ.get("DSH_AGENTS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".agents").resolve()


def resolve_project_root(project: str | None) -> Path:
    if project:
        return Path(project).resolve()
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def collect_source_files(source: Path) -> list[tuple[str, Path, str]]:
    """Return (relative_posix_path, absolute_path, manifest_role)."""
    patterns = [
        ("runtime", "runtime/**/*.py", "runtime"),
        ("contracts", "contracts/*.json", "schema"),
        ("tools", "tools/**/*.py", "other"),
        ("knowledge", "knowledge/**/*.*", "knowledge"),
    ]
    collected: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    for _, pattern, role in patterns:
        for path in sorted(source.glob(pattern)):
            if not path.is_file():
                continue
            if any(part in EXCLUDE for part in path.parts):
                continue
            relative = path.relative_to(source).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            collected.append((relative, path, role))
    if not collected:
        raise SystemExit(f"no suite files found under {source}")
    for name in ("setup_skill.py", "uninstall_skill.py"):
        candidate = source / "scripts" / name
        if not candidate.is_file():
            candidate = source / name
        if not candidate.is_file():
            candidate = Path(__file__).resolve().parent / name
        if candidate.is_file() and name not in seen:
            seen.add(name)
            collected.append((name, candidate, "launcher"))
    for name, role in (
        ("LICENSE", "license"),
        ("THIRD_PARTY_NOTICES.md", "license"),
        ("requirements.txt", "docs"),
        ("requirements.lock", "docs"),
    ):
        candidate = source / name
        if not candidate.is_file():
            candidate = REPO_ROOT / name
        if candidate.is_file() and name not in seen:
            seen.add(name)
            collected.append((name, candidate, role))
    return collected


def collect_skill_files(source: Path, skill: str) -> list[tuple[str, Path]]:
    base = source / "skills" / skill
    if not base.is_dir():
        raise SystemExit(f"skill source missing: {base}")
    files: list[tuple[str, Path]] = []
    for pattern in ("SKILL.md", "references/**/*.md", "scripts/launch.py"):
        for path in sorted(base.glob(pattern)):
            if path.is_file():
                files.append((path.relative_to(base).as_posix(), path))
    names = {name for name, _ in files}
    for required in ("SKILL.md", "scripts/launch.py"):
        if required not in names:
            raise SystemExit(f"{base} lacks required file {required}")
    return files


def build_manifest(source: Path, version: str, files: list[tuple[str, Path, str]]) -> dict:
    entries = []
    for relative, path, role in files:
        entries.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "role": role,
            }
        )
    files_payload = sorted(entries, key=lambda item: item["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "suite_version": version,
        "generated_at": now(),
        "builder": f"setup_skill.py/{SCHEMA_VERSION}",
        "target_platform": {
            "os": "windows",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "node": None,
        },
        "normalization": {
            "path_separator": "/",
            "case_policy": "casefolded_windows",
            "eol_normalized": False,
        },
        "files": files_payload,
        "excluded_patterns": ["**/__pycache__/**", "**/*.pyc", ".venv/**", ".pytest_cache/**"],
        "include_launcher": True,
        "include_schemas": True,
        "include_licenses": False,
        "bundle_sha256": contracts.sha256_json(files_payload),
    }


def install_records(agents_home: Path) -> list[dict]:
    state = agents_home / "uiux-suite" / "state"
    records = []
    if state.is_dir():
        for path in sorted(state.glob("install-*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return records


def owned_relative_paths(agents_home: Path) -> set[str]:
    owned: set[str] = set()
    for record in install_records(agents_home):
        for entry in record.get("files", []):
            owned.add(entry["path"])
    return owned


def record_path(agents_home: Path, version: str) -> Path:
    return agents_home / "uiux-suite" / "state" / f"install-{version}.json"


def active_version(agents_home: Path) -> str | None:
    link = agents_home / "skills" / "uiux" / "suite-link.json"
    if not link.is_file():
        return None
    try:
        return json.loads(link.read_text(encoding="utf-8")).get("active_version")
    except (OSError, ValueError):
        return None


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def suite_link_payload(agents_home: Path, suite_root: Path, skill_root: Path, version: str, python_exe: str | None) -> dict:
    try:
        relative = Path(os.path.relpath(suite_root, skill_root)).as_posix()
        path_kind = "relative_to_skill_root"
        suite_value = relative
    except ValueError:
        path_kind = "absolute"
        suite_value = str(suite_root)
    record = record_path(agents_home, version)
    try:
        record_relative: str | None = Path(os.path.relpath(record, skill_root)).as_posix()
    except ValueError:
        record_relative = None
    return {
        "schema_version": SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "active_version": version,
        "path_kind": path_kind,
        "suite_root": suite_value,
        "manifest_relpath": MANIFEST_NAME,
        "python_exe": python_exe,
        "created_by_installer": True,
        "created_at": now(),
        "install_record_relpath": record_relative,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_install(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve() if args.source else REPO_ROOT
    version = args.version or DEFAULT_VERSION
    agents_home = resolve_agents_home(args.scope, args.project)
    suite_root = agents_home / "uiux-suite" / "versions" / version
    skills_root = agents_home / "skills"
    owned = owned_relative_paths(agents_home)

    suite_files = collect_source_files(source)
    skill_files = {skill: collect_skill_files(source, skill) for skill in SKILLS}

    existing = installed = active_version(agents_home)
    if suite_root.exists() and not record_path(agents_home, version).is_file():
        return emit(
            {"ok": False, "code": "SUITE_EXISTS", "suite_root": str(suite_root), "detail": "existing suite root without install record"},
            10,
        )

    # Safety: every existing destination must be owned by a prior install record.
    planned: list[tuple[Path, Path]] = []
    for relative, path, _role in suite_files:
        planned.append((path, suite_root / relative))
    for skill in SKILLS:
        for relative, path in skill_files[skill]:
            planned.append((path, skills_root / skill / relative))
    for _source_path, destination in planned:
        if destination.exists() and not destination.is_file():
            return emit({"ok": False, "code": "PATH_CONFLICT", "path": str(destination)}, 10)
        if destination.exists():
            try:
                relative_to_home = destination.relative_to(agents_home).as_posix()
            except ValueError:
                return emit({"ok": False, "code": "UNAUTHORIZED_PATH", "path": str(destination)}, 10)
            if relative_to_home not in owned:
                return emit(
                    {"ok": False, "code": "SKILL_EXISTS", "path": str(destination), "detail": "existing file not owned by this installer"},
                    10,
                )

    copied: list[dict] = []
    for relative, path, _role in suite_files:
        destination = suite_root / relative
        copy_file(path, destination)
        copied.append({"path": destination.relative_to(agents_home).as_posix(), "sha256": sha256_file(destination)})

    manifest = build_manifest(source, version, suite_files)
    manifest_errors = contracts.validation_errors("release-manifest", manifest)
    if manifest_errors:
        return emit({"ok": False, "code": "MANIFEST_INVALID", "errors": manifest_errors}, 10)
    write_json(suite_root / MANIFEST_NAME, manifest)
    copied.append(
        {
            "path": (suite_root / MANIFEST_NAME).relative_to(agents_home).as_posix(),
            "sha256": sha256_file(suite_root / MANIFEST_NAME),
        }
    )

    should_activate = existing is None or version_tuple(version) >= version_tuple(existing)
    python_exe = select_python_exe(getattr(args, "python_exe", None))
    if python_exe is None:
        python_exe = sys.executable if Path(sys.executable).is_file() else None
    if should_activate:
        for skill in SKILLS:
            skill_root = skills_root / skill
            for relative, path in skill_files[skill]:
                destination = skill_root / relative
                copy_file(path, destination)
                copied.append({"path": destination.relative_to(agents_home).as_posix(), "sha256": sha256_file(destination)})
            link = suite_link_payload(agents_home, suite_root, skill_root, version, python_exe)
            link_errors = contracts.validation_errors("suite-link", link)
            if link_errors:
                return emit({"ok": False, "code": "LINK_INVALID", "errors": link_errors}, 10)
            write_json(skill_root / "suite-link.json", link)
            copied.append(
                {
                    "path": (skill_root / "suite-link.json").relative_to(agents_home).as_posix(),
                    "sha256": sha256_file(skill_root / "suite-link.json"),
                }
            )

    record = {
        "schema_version": SCHEMA_VERSION,
        "suite_id": SUITE_ID,
        "version": version,
        "scope": args.scope,
        "host": args.host,
        "installed_at": now(),
        "agents_home": str(agents_home),
        "suite_root": str(suite_root),
        "installed_from_source": str(source),
        "installed_from_commit": source_commit(source),
        "activated": should_activate,
        "python_exe": python_exe,
        "python_version": python_version_of(python_exe),
        "files": sorted(copied, key=lambda item: item["path"]),
    }
    write_json(record_path(agents_home, version), record)

    return emit(
        {
            "ok": True,
            "installed": True,
            "version": version,
            "scope": args.scope,
            "agents_home": str(agents_home),
            "suite_root": str(suite_root),
            "skills_root": str(skills_root),
            "activated": should_activate,
            "files": len(copied),
        },
        0,
    )


def scan_skill_root(root: Path) -> list[dict]:
    entries = []
    if not root.is_dir():
        return entries
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            entries.append({"name": child.name, "path": child})
        elif child.is_file() and child.suffix == ".md":
            entries.append({"name": child.stem, "path": child})
    return entries


def host_roots(project_root: Path) -> list[dict]:
    dsh_home = Path(os.environ.get("DSH_HOME", str(Path.home() / ".dsh"))).expanduser().resolve()
    agents_home = Path(os.environ.get("DSH_AGENTS_HOME", str(Path.home() / ".agents"))).expanduser().resolve()
    roots = [
        {"source": "project-dsh", "rank": 100, "path": project_root / ".dsh" / "skills"},
        {"source": "project-agents", "rank": 200, "path": project_root / ".agents" / "skills"},
    ]
    custom = os.environ.get("UIUX_CUSTOM_SKILLS_HOME")
    if custom:
        roots.append({"source": "custom", "rank": 300, "path": Path(custom).expanduser().resolve()})
    roots.extend(
        [
            {"source": "user-dsh", "rank": 400, "path": dsh_home / "skills"},
            {"source": "user-agents", "rank": 500, "path": agents_home / "skills"},
        ]
    )
    return roots


def check_link(agents_home: Path, skill: str) -> tuple[dict | None, list[str]]:
    skill_root = agents_home / "skills" / skill
    link_path = skill_root / "suite-link.json"
    problems: list[str] = []
    if not link_path.is_file():
        return None, ["LINK_MISSING"]
    try:
        link = json.loads(link_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, ["LINK_INVALID"]
    errors = contracts.validation_errors("suite-link", link)
    if errors:
        return link, ["LINK_INVALID: " + "; ".join(errors[:2])]
    suite_root = (skill_root / link["suite_root"]).resolve() if link["path_kind"] == "relative_to_skill_root" else Path(link["suite_root"]).resolve()
    if not suite_root.is_dir():
        return link, ["RELEASE_ROOT_MISSING"]
    manifest_path = suite_root / link["manifest_relpath"]
    if not manifest_path.is_file():
        return link, ["MANIFEST_CORRUPT"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("suite_version") != link["active_version"]:
        return link, ["VERSION_MISMATCH"]
    bad = [entry["path"] for entry in manifest.get("files", []) if not (suite_root / entry["path"]).is_file()]
    if bad:
        return link, [f"MANIFEST_MISMATCH: missing {len(bad)} file(s)"]
    mismatch = [
        entry["path"]
        for entry in manifest.get("files", [])
        if sha256_file(suite_root / entry["path"]) != entry["sha256"]
    ]
    if mismatch:
        return link, [f"MANIFEST_MISMATCH: hash differs for {len(mismatch)} file(s)"]
    python_exe = link.get("python_exe")
    if python_exe and not Path(python_exe).is_file():
        # Launcher falls back to sys.executable/PATH; doctor validates the actual choice below.
        pass
    return link, problems


def cmd_doctor(args: argparse.Namespace) -> int:
    agents_home = resolve_agents_home(args.scope, args.project)
    project_root = resolve_project_root(args.project or (None if args.scope == "user" else "."))
    problems: list[str] = []
    checks: list[dict] = []
    entries: list[dict] = []
    roots = host_roots(project_root)

    for root in roots:
        for entry in scan_skill_root(root["path"]):
            entries.append(
                {
                    "name": entry["name"],
                    "root": str(entry["path"]),
                    "rank": root["rank"],
                    "shadowed_by": None,
                }
            )
    winners: dict[str, dict] = {}
    for entry in sorted(entries, key=lambda item: item["rank"]):
        if entry["name"] in winners:
            entry["shadowed_by"] = winners[entry["name"]]["root"]
        else:
            winners[entry["name"]] = entry

    link_status: dict[str, dict] = {}
    link_objects: dict[str, dict] = {}
    for skill in SKILLS:
        link, skill_problems = check_link(agents_home, skill)
        link_objects[skill] = link or {}
        problems.extend(f"{skill}: {problem}" for problem in skill_problems)
        link_status[skill] = {
            "found": link is not None,
            "problems": skill_problems,
            "active_version": (link or {}).get("active_version"),
            "suite_root": (link or {}).get("suite_root"),
        }
        checks.append(
            {
                "id": f"skill:{skill}",
                "status": "READY" if not skill_problems else "INCOMPATIBLE",
                "detail": "linked and manifest-verified" if not skill_problems else "; ".join(skill_problems),
            }
        )

    linked_python = (link_objects.get("uiux") or {}).get("python_exe") or sys.executable
    if not Path(linked_python).is_file():
        linked_python = shutil.which("python") or sys.executable
    python_version = python_version_of(linked_python)
    try:
        python_supported = tuple(int(part) for part in (python_version or "0").split(".")[:2]) >= (3, 10)
    except ValueError:
        python_supported = False
    python_ok = Path(linked_python).is_file() and python_works(linked_python) and python_supported
    checks.append(
        {
            "id": "python",
            "status": "READY" if python_ok else "INCOMPATIBLE",
            "detail": f"{linked_python} ({python_version or 'unknown'})",
        }
    )
    if not python_ok:
        problems.append(f"python: unusable or below 3.10: {linked_python}")
    jsonschema_version = dependency_version_of(linked_python, "jsonschema")
    try:
        jsonschema_ok = bool(jsonschema_version) and tuple(
            int(part) for part in jsonschema_version.split(".")[:2]
        ) >= (4, 20) and int(jsonschema_version.split(".")[0]) == 4
    except (ValueError, IndexError):
        jsonschema_ok = False
    checks.append(
        {
            "id": "jsonschema",
            "status": "READY" if jsonschema_ok else "INCOMPATIBLE",
            "detail": jsonschema_version or "not importable",
        }
    )
    if not jsonschema_ok:
        problems.append(f"jsonschema: requires >=4.20,<5, found {jsonschema_version or 'none'}")
    checks.append(
        {
            "id": "python_runner",
            "status": "READY",
            "detail": f"{sys.executable} ({sys.version.split()[0]})",
        }
    )
    node = shutil.which("node")
    node_version = None
    if node:
        try:
            node_proc = subprocess.run(
                [node, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15
            )
            node_version = node_proc.stdout.strip() if node_proc.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            node_version = None
    node_major = 0
    if node_version:
        try:
            node_major = int(node_version.lstrip("v").split(".")[0])
        except ValueError:
            node_major = 0
    node_ok = bool(node) and node_major >= 20
    checks.append(
        {
            "id": "node",
            "status": "READY" if node_ok else ("INCOMPATIBLE" if node else "MISSING"),
            "detail": f"{node or 'node not on PATH'} ({node_version or 'unknown'})",
        }
    )
    if not node_ok:
        problems.append(f"node: requires >=20, found {node or 'none'} ({node_version or 'unknown'})")
    gui_ok = os.name == "nt"
    checks.append({"id": "gui", "status": "READY" if gui_ok else "UNVERIFIED", "detail": "windows desktop" if gui_ok else "non-Windows host"})
    writable = os.access(agents_home, os.W_OK) if agents_home.exists() else True
    checks.append({"id": "file_permissions", "status": "READY" if writable else "INCOMPATIBLE", "detail": str(agents_home)})
    checks.append({"id": "mcp", "status": "UNVERIFIED", "detail": "not exercised by doctor"})
    checks.append({"id": "resume", "status": "UNVERIFIED", "detail": "not exercised by doctor"})

    statuses = [check["status"] for check in checks]
    if "INCOMPATIBLE" in statuses:
        overall = "INCOMPATIBLE"
    elif "MISSING" in statuses:
        overall = "MISSING"
    elif "UNVERIFIED" in statuses:
        overall = "UNVERIFIED"
    else:
        overall = "READY"

    record = {
        "schema_version": SCHEMA_VERSION,
        "host": args.host,
        "host_version": None,
        "os": f"{os.name}-{sys.platform}",
        "python": python_version or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "node": node,
        "skill_roots": [
            {"path": str(root["path"]), "rank": root["rank"], "source": root["source"], "exists": root["path"].is_dir()}
            for root in roots
        ],
        "entries": entries,
        "capabilities": {
            "skill_discovery": "READY" if any(link_status[skill]["found"] for skill in SKILLS) else "MISSING",
            "script_exec": "READY" if python_ok else "MISSING",
            "gui_access": "READY" if gui_ok else "UNVERIFIED",
            "mcp": "UNVERIFIED",
            "file_permissions": "READY" if writable else "INCOMPATIBLE",
            "resume": "UNVERIFIED",
        },
        "checks": checks,
        "doctor_version": SCHEMA_VERSION,
        "overall_status": overall,
        "checked_at": now(),
    }
    errors = contracts.validation_errors("host-capability", record)
    if errors:
        return emit({"ok": False, "code": "HOST_CAPABILITY_INVALID", "errors": errors, "record": record}, 10)

    if args.out:
        write_json(Path(args.out), record)
    emit({"ok": overall != "INCOMPATIBLE", "overall_status": overall, "links": link_status, "problems": problems, "host_capability": record}, 0 if overall in ("READY", "UNVERIFIED") else 11)
    return 0 if overall in ("READY", "UNVERIFIED") else 11


def cmd_repair(args: argparse.Namespace) -> int:
    agents_home = resolve_agents_home(args.scope, args.project)
    version = args.version or active_version(agents_home)
    if not version:
        return emit({"ok": False, "code": "LINK_MISSING", "detail": "no active version"}, 10)
    record_file = record_path(agents_home, version)
    if not record_file.is_file():
        return emit({"ok": False, "code": "INSTALL_RECORD_MISSING", "path": str(record_file)}, 10)
    record = json.loads(record_file.read_text(encoding="utf-8"))
    suite_root = Path(record["suite_root"])
    missing = [entry["path"] for entry in record["files"] if not (agents_home / entry["path"]).is_file()]
    if missing:
        return emit({"ok": False, "code": "FILES_MISSING", "missing": missing[:20]}, 10)
    python_exe = record.get("python_exe")
    repaired = []
    for skill in SKILLS:
        skill_root = agents_home / "skills" / skill
        if not (skill_root / "SKILL.md").is_file():
            continue
        link = suite_link_payload(agents_home, suite_root, skill_root, version, python_exe)
        write_json(skill_root / "suite-link.json", link)
        repaired.append(skill)
    emit({"ok": True, "version": version, "repaired_links": repaired}, 0)
    return 0


def write_active_links(agents_home: Path, version: str, suite_root: Path, python_exe: str | None) -> list[str]:
    activated: list[str] = []
    for skill in SKILLS:
        skill_root = agents_home / "skills" / skill
        if not (skill_root / "SKILL.md").is_file():
            continue
        link = suite_link_payload(agents_home, suite_root, skill_root, version, python_exe)
        errors = contracts.validation_errors("suite-link", link)
        if errors:
            raise SystemExit(f"invalid suite-link for {skill}: {errors}")
        write_json(skill_root / "suite-link.json", link)
        activated.append(skill)
    return activated


def cmd_upgrade(args: argparse.Namespace) -> int:
    agents_home = resolve_agents_home(args.scope, args.project)
    current = active_version(agents_home)
    if current and version_tuple(args.version) <= version_tuple(current):
        return emit({"ok": False, "code": "UPGRADE_NOT_NEWER", "current": current, "target": args.version}, 10)
    if not record_path(agents_home, args.version).is_file() and not args.source:
        return emit(
            {"ok": False, "code": "SOURCE_REQUIRED", "detail": "upgrade needs --source when target version is not installed"},
            10,
        )
    return cmd_install(args)


def cmd_rollback(args: argparse.Namespace) -> int:
    agents_home = resolve_agents_home(args.scope, args.project)
    record_file = record_path(agents_home, args.version)
    if not record_file.is_file():
        return emit({"ok": False, "code": "INSTALL_RECORD_MISSING", "version": args.version}, 10)
    record = json.loads(record_file.read_text(encoding="utf-8"))
    suite_root = Path(record["suite_root"])
    if not suite_root.is_dir():
        return emit({"ok": False, "code": "RELEASE_ROOT_MISSING", "suite_root": str(suite_root)}, 10)
    activated = write_active_links(agents_home, args.version, suite_root, record.get("python_exe"))
    return emit({"ok": True, "rolled_back_to": args.version, "activated": activated}, 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setup_skill.py")
    parser.add_argument("--host", default="dsh")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install")
    install.add_argument("--scope", choices=["user", "project"], default="user")
    install.add_argument("--project")
    install.add_argument("--source")
    install.add_argument("--version", default=DEFAULT_VERSION)
    install.add_argument("--python-exe", help="explicit Python for suite-link (must import jsonschema)")
    install.set_defaults(func=cmd_install, host="dsh")

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--scope", choices=["user", "project"], default="user")
    doctor.add_argument("--project")
    doctor.add_argument("--out")
    doctor.set_defaults(func=cmd_doctor, host="dsh")

    repair = sub.add_parser("repair")
    repair.add_argument("--scope", choices=["user", "project"], default="user")
    repair.add_argument("--project")
    repair.add_argument("--version")
    repair.set_defaults(func=cmd_repair, host="dsh")

    upgrade = sub.add_parser("upgrade")
    upgrade.add_argument("--scope", choices=["user", "project"], default="user")
    upgrade.add_argument("--project")
    upgrade.add_argument("--source")
    upgrade.add_argument("--version", required=True)
    upgrade.add_argument("--python-exe", help="explicit Python for suite-link")
    upgrade.set_defaults(func=cmd_upgrade, host="dsh")

    rollback = sub.add_parser("rollback")
    rollback.add_argument("--scope", choices=["user", "project"], default="user")
    rollback.add_argument("--project")
    rollback.add_argument("--version", required=True)
    rollback.set_defaults(func=cmd_rollback, host="dsh")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
