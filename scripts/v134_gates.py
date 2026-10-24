"""V1.3.4 release-gate checkers (R0–R4, R8).

R0–R9 are release gates that reuse underlying G0–G5 facts; they must not create a
second authoritative evidence source. Each gate writes a JSON record under the
acceptance root and exits non-zero on FAIL/BLOCKED.

Usage:
  python scripts/v134_gates.py --gate R0
  python scripts/v134_gates.py --gate all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ROOT = Path(r"G:\AI\uiux-v134")
EVIDENCE = ACCEPTANCE_ROOT / "evidence" / "gates"
SOURCE_REPO = Path(r"G:\AI\universal-uiux-engineering")
BASE_COMMIT = "314e803ceaec6e03781da2c6e94bb548297b95a8"
V133_ZIP_SHA256 = "a348c0888ea70aad3b2a50103b8c5bd5eaf3a365f7d035d889e67b952a410526"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return proc.stdout.strip()


def pytest(paths: list[str], extra: list[str] | None = None) -> dict:
    env = {"PYTHONPATH": str(SUITE_ROOT / "runtime"), "PYTHONDONTWRITEBYTECODE": "1"}
    import os

    full_env = dict(os.environ)
    full_env.update(env)
    argv = [sys.executable, "-m", "pytest", *paths, "-q", "--no-header", "-p", "no:cacheprovider"]
    proc = subprocess.run(
        argv, cwd=str(SUITE_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900, env=full_env,
    )
    tail = [line for line in proc.stdout.splitlines() if line.strip()][-1:] or ["<no output>"]
    return {
        "cmd": " ".join(paths),
        "exit_code": proc.returncode,
        "summary": tail[0],
        "ok": proc.returncode == 0,
    }


def check(name: str, ok: bool, detail: str, blocking: bool = True) -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail, "blocking": blocking}


def r0() -> dict:
    checks = []
    source_status = git(SOURCE_REPO, "status", "--porcelain")
    untracked = [line[3:] for line in source_status.splitlines() if line.startswith("?? ")]
    checks.append(check("source_head", bool(git(SOURCE_REPO, "rev-parse", "HEAD")), git(SOURCE_REPO, "rev-parse", "HEAD")))
    checks.append(check("v133_tag_present", bool(git(SOURCE_REPO, "tag", "--list", "v1.3.3")),
                        git(SOURCE_REPO, "rev-list", "-n", "1", "v1.3.3")))
    zip_path = SOURCE_REPO / "dist" / "uiux-suite-1.3.3-win64.zip"
    zip_ok = zip_path.is_file() and sha256_file(zip_path) == V133_ZIP_SHA256
    checks.append(check("v133_zip_unchanged", zip_ok, sha256_file(zip_path) if zip_path.is_file() else "missing"))
    expected_untracked = {
        "evidence/T5.5/formal-install-doctor.txt",
        "evidence/T5.5/formal-install-install.txt",
        "evidence/T5.5/formal-install-uninstall.txt",
        "evidence/T5.5/formal-install-upgrade.txt",
        "evidence/T5.5/formal-install.json",
    }
    checks.append(check(
        "historical_untracked_preserved",
        set(untracked) == expected_untracked,
        f"untracked={sorted(untracked)}",
    ))
    checks.append(check(
        "no_other_source_changes",
        len(source_status.splitlines()) == len(untracked),
        f"status_lines={len(source_status.splitlines())}",
    ))
    branch = git(SUITE_ROOT, "rev-parse", "--abbrev-ref", "HEAD")
    checks.append(check("impl_branch", branch == "v1.3.4-hardening", branch))
    checks.append(check("impl_base", git(SUITE_ROOT, "merge-base", "HEAD", BASE_COMMIT) == BASE_COMMIT,
                        f"merge-base={git(SUITE_ROOT, 'merge-base', 'HEAD', BASE_COMMIT)}"))
    return {"gate": "R0", "state": "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", "checks": checks}


def r1() -> dict:
    checks = []
    v133 = sorted((SUITE_ROOT / "contracts").glob("*.v1.3.3.schema.json"))
    v134 = sorted((SUITE_ROOT / "contracts").glob("*.v1.3.4.schema.json"))
    checks.append(check("v133_schema_count", len(v133) == 26, str(len(v133))))
    checks.append(check("v134_schema_count", len(v134) == 26, str(len(v134))))
    checks.append(check("v133_untouched_in_git", git(SUITE_ROOT, "status", "--porcelain", "contracts") == "",
                        "contracts/ clean"))
    bad_refs = []
    for path in v134:
        text = path.read_text(encoding="utf-8")
        if "v1.3.3.schema.json" in text:
            bad_refs.append(path.name)
    checks.append(check("v134_no_v133_refs", not bad_refs, f"bad={bad_refs}"))
    checks.append(check("enums_pair", (SUITE_ROOT / "contracts" / "enums.v1.3.3.json").is_file()
                        and (SUITE_ROOT / "contracts" / "enums.v1.3.4.json").is_file(), "enums v1.3.3+v1.3.4"))
    checks.append(check("policy_pair", (SUITE_ROOT / "contracts" / "mode-gate-policy.v1.3.3.json").is_file()
                        and (SUITE_ROOT / "contracts" / "mode-gate-policy.v1.3.4.json").is_file(),
                        "mode-gate-policy v1.3.3+v1.3.4"))
    migration = SUITE_ROOT / "docs" / "MIGRATION_V1.3.3_TO_V1.3.4.md"
    checks.append(check("migration_matrix", migration.is_file()
                        and "强制兼容用例" in migration.read_text(encoding="utf-8"),
                        str(migration)))
    test = pytest(["tests/unit/test_version_dispatch.py"])
    checks.append(check("version_dispatch_tests", test["ok"], test["summary"]))
    return {"gate": "R1", "state": "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL",
            "checks": checks, "tests": test}


def r2() -> dict:
    checks = []
    sys.path.insert(0, str(SUITE_ROOT / "runtime"))
    from uiux_engine import fixture as fixture_mod

    fixture_files = sorted((SUITE_ROOT / "fixtures" / "**" / "*.json").glob("*.json")) if False else [
        SUITE_ROOT / "fixtures" / "new-manga" / "minimal.json",
        SUITE_ROOT / "fixtures" / "generic" / "web-minimal.json",
    ]
    load_ok = []
    for path in fixture_files:
        try:
            fixture_mod.load_fixture(path)
            load_ok.append(path.name)
        except Exception as exc:  # noqa: BLE001
            load_ok.append(f"{path.name}: {exc}")
    checks.append(check("builtin_fixtures_load", all(":" not in item for item in load_ok), str(load_ok)))
    matrix = fixture_mod.failure_class_matrix()
    checks.append(check("failure_classes_complete",
                        {item["class"] for item in matrix} == set(fixture_mod.FAILURE_CLASSES),
                        f"{len(matrix)} classes"))
    checks.append(check("ab_attribution_rule",
                        fixture_mod.classify_ab_attribution(
                            bad_problems=[{"class": "missing_executable"}], good_problems=[],
                        )["environment_authored"] is True,
                        "environment-authored detection"))
    test = pytest(["tests/unit/test_fixture.py"])
    checks.append(check("fixture_tests", test["ok"], test["summary"]))
    return {"gate": "R2", "state": "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL",
            "checks": checks, "tests": test}


def r3() -> dict:
    checks = []
    sys.path.insert(0, str(SUITE_ROOT / "runtime"))
    from uiux_engine import inventory as inv

    template = SUITE_ROOT / "inventory" / "templates" / "new-manga-v134.json"
    payload = inv.load_inventory(template)
    frozen = inv.freeze(payload, reviewed_by="lead")
    checks.append(check("template_loads", payload["inventory_id"] == "INV-NEW-MANGA-V134", payload["inventory_id"]))
    checks.append(check("baseline_frozen", inv.verify_baseline(frozen) == [], frozen["scope"]["baseline_hash"]))
    stats = inv.mapping_stats(frozen, [])
    checks.append(check("declared_scope_ratio_only",
                        stats["full_product_coverage"] == "UNKNOWN"
                        and stats["ratios"]["declared_scope_mapping_ratio"] == 0.0,
                        f"cov={stats['full_product_coverage']}"))
    checks.append(check("risk_gate_blocks_unverified", stats["risk_gate"]["blocked"] is True,
                        str(stats["risk_gate"]["blocking_items"][:3])))
    tampered = json.loads(json.dumps(frozen))
    tampered["items"][0]["risk_level"] = "P3"
    checks.append(check("baseline_tamper_detected",
                        any("BASELINE_MISMATCH" in p for p in inv.verify_baseline(tampered)), "tamper"))
    test = pytest(["tests/unit/test_inventory.py"])
    checks.append(check("inventory_tests", test["ok"], test["summary"]))
    return {"gate": "R3", "state": "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL",
            "checks": checks, "tests": test}


def r4() -> dict:
    checks = []
    test_evidence = pytest(["tests/unit/test_integrity_safety.py"])
    checks.append(check("integrity_safety_tests", test_evidence["ok"], test_evidence["summary"]))
    test_schemas = pytest(["tests/unit/test_schemas.py"])
    checks.append(check("schema_evidence_tests", test_schemas["ok"], test_schemas["summary"]))
    test_finalize = pytest(["tests/integration/test_finalize.py"])
    checks.append(check("finalize_regression", test_finalize["ok"], test_finalize["summary"]))
    return {"gate": "R4", "state": "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL",
            "checks": checks, "tests": [test_evidence, test_schemas, test_finalize]}


def r8() -> dict:
    checks = []
    full = pytest(["tests"])
    checks.append(check("full_test_suite", full["ok"], full["summary"]))
    attack = subprocess.run(
        [sys.executable, str(SUITE_ROOT / "scripts" / "run_attack_suite.py")],
        cwd=str(SUITE_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
        env={**__import__("os").environ, "PYTHONPATH": str(SUITE_ROOT / "runtime")},
    )
    attack_ok = attack.returncode == 0
    checks.append(check("attack_suite", attack_ok, (attack.stdout.strip().splitlines() or ["<none>"])[-1]))
    stage1 = subprocess.run(
        [sys.executable, str(SUITE_ROOT / "scripts" / "run_stage1_suite.py")],
        cwd=str(SUITE_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
        env={**__import__("os").environ, "PYTHONPATH": str(SUITE_ROOT / "runtime")},
    )
    stage1_ok = stage1.returncode == 0
    checks.append(check("stage1_suite", stage1_ok, (stage1.stdout.strip().splitlines() or ["<none>"])[-1]))
    return {"gate": "R8", "state": "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL",
            "checks": checks, "tests": [full], "attack_exit": attack.returncode, "stage1_exit": stage1.returncode}


GATES = {"R0": r0, "R1": r1, "R2": r2, "R3": r3, "R4": r4, "R8": r8}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", choices=[*GATES, "all"], default="all")
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = []
    gates = list(GATES) if args.gate == "all" else [args.gate]
    for name in gates:
        result = GATES[name]()
        result["computed_at"] = now()
        result["suite_commit"] = git(SUITE_ROOT, "rev-parse", "HEAD")
        out = EVIDENCE / f"{name}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["evidence_file"] = str(out)
        results.append(result)
        print(json.dumps({
            "gate": result["gate"], "state": result["state"], "evidence": str(out),
            "failed": [c["check"] for c in result["checks"] if not c["ok"]],
        }, ensure_ascii=False))
    bad = [r for r in results if r["state"] != "PASS"]
    return 0 if not bad else 10


if __name__ == "__main__":
    raise SystemExit(main())
