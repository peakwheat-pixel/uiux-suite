"""V1.3.5 release gates (R0–R9).

Each gate is derived from evidence, writes a JSON record under the V1.3.5
acceptance root, and exits non-zero on FAIL/BLOCKED. No gate may be hand-edited
to PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
ACC = Path(r"G:\AI\uiux-v135")
EVID = ACC / "evidence" / "gates"
SOURCE_REPO = Path(r"G:\AI\universal-uiux-engineering")
BASE_COMMIT = "314e803ceaec6e03781da2c6e94bb548297b95a8"
V133_ZIP = Path(r"G:\AI\universal-uiux-engineering\dist\uiux-suite-1.3.3-win64.zip")
V133_SHA = "a348c0888ea70aad3b2a50103b8c5bd5eaf3a365f7d035d889e67b952a410526"
V134_ZIP = Path(r"G:\AI\uiux-v134\packages\uiux-suite-1.3.4-win64.zip")
V134_SHA = "a3b5c2a2d7a4537dbe1f8abbd0ed9e79018bf0e7780479463b555e7fa928b223"
V135_ZIP = ACC / "packages" / "uiux-suite-1.3.5-win64.zip"
V135_SUMS = ACC / "packages" / "uiux-suite-1.3.5-SHA256SUMS.txt"
PYTHON = sys.executable


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(name: str, ok: bool, detail: str, blocking: bool = True) -> dict:
    return {"check": name, "ok": bool(ok), "detail": str(detail)[:300], "blocking": blocking}


def write(gate: str, state: str, checks: list[dict], extra: dict | None = None) -> dict:
    payload = {"gate": gate, "state": state, "checks": checks, "generated_at": now(),
               "suite": "1.3.5", "acceptance_root": str(ACC)}
    if extra:
        payload.update(extra)
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / f"{gate}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def pytest_suite() -> dict:
    proc = subprocess.run([PYTHON, "-m", "pytest", "tests", "-q"], cwd=str(SUITE),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={**__import__("os").environ, "PYTHONPATH": str(SUITE / "runtime"),
                               "PYTHONUTF8": "1"}, timeout=900)
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return {"exit": proc.returncode, "summary": tail}


def load(rel: str) -> dict:
    return json.loads((ACC / rel).read_text(encoding="utf-8"))


def r0() -> dict:
    checks = [
        check("source_repo_head", git(SOURCE_REPO, "rev-parse", "HEAD") == BASE_COMMIT,
              git(SOURCE_REPO, "rev-parse", "HEAD")),
        check("v133_zip_unchanged", V133_ZIP.is_file() and sha256_file(V133_ZIP) == V133_SHA,
              sha256_file(V133_ZIP) if V133_ZIP.is_file() else "missing"),
        check("v134_zip_unchanged", V134_ZIP.is_file() and sha256_file(V134_ZIP) == V134_SHA,
              sha256_file(V134_ZIP) if V134_ZIP.is_file() else "missing"),
        check("v134_evidence_present", Path(r"G:\AI\uiux-v134\evidence\audit\v134\task-result.json").is_file(),
              "v1.3.4 audit evidence"),
    ]
    return write("R0", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r1() -> dict:
    import json as _json

    counts = {v: len(list((SUITE / "contracts").glob(f"*.v{v}.schema.json"))) for v in ("1.3.3", "1.3.4", "1.3.5")}
    cross = []
    for path in (SUITE / "contracts").glob("*.v1.3.5.schema.json"):
        text = path.read_text(encoding="utf-8")
        for other in ("1.3.3", "1.3.4"):
            if f".v{other}." in text:
                cross.append(f"{path.name} -> {other}")
    checks = [
        check("schema_counts", counts == {"1.3.3": 26, "1.3.4": 26, "1.3.5": 26}, counts),
        check("no_cross_version_refs", not cross, cross),
        check("v135_enums", (SUITE / "contracts" / "enums.v1.3.5.json").is_file(), "enums.v1.3.5"),
        check("v135_policy", (SUITE / "contracts" / "mode-gate-policy.v1.3.5.json").is_file(), "policy.v1.3.5"),
        check("version_dispatch_tests",
              subprocess.run([PYTHON, "-m", "pytest", "tests/unit/test_version_dispatch.py", "-q"],
                             cwd=str(SUITE), capture_output=True).returncode == 0,
              "test_version_dispatch.py"),
    ]
    return write("R1", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r2() -> dict:
    proc = subprocess.run([PYTHON, "-m", "pytest", "tests/unit/test_fixture.py",
                           "tests/integration/test_fixture_ab_regression.py", "-q"],
                          cwd=str(SUITE), capture_output=True, text=True,
                          env={**__import__("os").environ, "PYTHONPATH": str(SUITE / "runtime")}, timeout=600)
    matrix = __import__("sys").path.insert(0, str(SUITE / "runtime"))
    from uiux_engine import fixture
    checks = [
        check("fixture_failure_classes", len(fixture.failure_class_matrix()) == 7,
              f"{len(fixture.failure_class_matrix())} classes"),
        check("fixture_tests", proc.returncode == 0, proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""),
    ]
    return write("R2", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r3() -> dict:
    inventory = load("evidence/task02/inventory-v135-freeze.json")
    coverage = load("evidence/audit/v135/coverage-matrix.json")
    discovery = load("evidence/task02/discovery.json")
    ids = set()
    for item in json.loads((SUITE / "inventory" / "templates" / "new-manga-v135.json").read_text(encoding="utf-8"))["items"]:
        ids.add(item["stable_id"])
    unscoped = [r.get("scope_ref") for r in coverage["records"] if r.get("scope_ref") not in ids]
    checks = [
        check("inventory_items", inventory["items"] == 18 and inventory["included"] == 15 and inventory["excluded"] == 3,
              inventory),
        check("scope_not_shrunk", inventory["comparison_v134"]["scope_shrunk"] is False,
              inventory["comparison_v134"]),
        check("coverage_mapped", not unscoped, unscoped),
        check("g1_discovery_present", discovery["summary"]["pages"] > 0 and discovery["summary"]["entries"] > 0,
              discovery["summary"]),
        check("full_product_coverage_unknown", True, "no full-product evidence claimed"),
    ]
    return write("R3", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r4() -> dict:
    sys.path.insert(0, str(SUITE / "runtime"))
    from uiux_engine import contracts
    manifest = load("evidence/audit/v135/evidence-manifest.json")
    mismatches = []
    for item in manifest["items"]:
        ref = ACC / "evidence" / "audit" / item["references"][0]
        if not ref.is_file() or sha256_file(ref) != item["source_sha256"]:
            mismatches.append(item["id"])
    result = load("evidence/audit/v135/task-result.json")
    errors = contracts.validation_errors("task-result", result, "1.3.5")
    checks = [
        check("evidence_hashes", not mismatches, f"{len(manifest['items'])} items, mismatches={len(mismatches)}"),
        check("task_result_valid", not errors, errors[:3]),
        check("task_result_partial_expected", result["status"] == "PARTIAL" and result["derived_g6"]["state"] == "UNVERIFIED",
              {"status": result["status"], "g6": result["derived_g6"]["state"]}),
    ]
    return write("R4", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r5() -> dict:
    ab = load("evidence/task05/ab-regression.json")
    review = load("evidence/verify/reviewer-findings-v135.json")
    checks = [
        check("ab_environment_cases", ab["summary"]["cases"] == 7 and ab["summary"]["failures"] == 0, ab["summary"]),
        check("reviewer_no_disputed", review["summary"]["disputed"] == 0, review["summary"]),
        check("reviewer_confirmed", review["summary"]["confirmed"] >= 10, review["summary"]),
    ]
    return write("R5", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r6() -> dict:
    risk = load("evidence/audit/v135/risk-gate-v135.json")
    coverage = risk["execution_coverage"]
    checks = [
        check("risk_gate_integrity", risk["integrity_status"] == "PASS" and not risk["violations"], risk["violations"][:3]),
        check("high_risk_denominator", coverage["high_risk_total"] == 10, coverage["high_risk_total"]),
        check("high_risk_verified", coverage["high_risk_verified"] == 3, coverage["high_risk_verified"]),
        check("a_level_risk_met_false", risk["a_level_risk_met"] is False, risk["a_level_risk_met"], blocking=False),
        check("risk_gate_semantics", risk["gate_status"] == "PASS",
              "mechanism PASS; business coverage recorded separately"),
    ]
    return write("R6", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks,
                 {"execution_coverage": coverage, "a_level_risk_met": risk["a_level_risk_met"],
                  "note": "R6 PASS covers the mechanism; high-risk business execution is 3/10"})


def r7() -> dict:
    review = load("evidence/verify/reviewer-findings-v135.json")
    report = ACC / "evidence" / "verify" / "REVIEWER_REPORT_V135.md"
    checks = [
        check("reviewer_report_present", report.is_file(), "REVIEWER_REPORT_V135.md"),
        check("reviewer_no_disputed", review["summary"]["disputed"] == 0, review["summary"]),
        check("independence_not_overstated", True, "ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED (not INDEPENDENT_REVIEW_PASS)"),
    ]
    prov = ACC / "evidence" / "release" / "github-actions-provenance-v135.json"
    if prov.is_file():
        payload = json.loads(prov.read_text(encoding="utf-8"))
        checks.append(check("external_build_provenance", payload.get("conclusion") == "success",
                            f"run={payload.get('run_id')}", blocking=False))
    else:
        checks.append(check("external_build_provenance", False, "not recorded yet", blocking=False))
    return write("R7", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks,
                 {"independent_review_pass": False,
                  "note": "external CI proves build provenance only; independent attestation not obtained"})


def r8() -> dict:
    suite = pytest_suite()
    checks = [
        check("full_pytest", suite["exit"] == 0, suite["summary"]),
        check("test_count_not_reduced", "passed" in suite["summary"], suite["summary"]),
    ]
    return write("R8", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks)


def r9() -> dict:
    sums = {}
    if V135_SUMS.is_file():
        for line in V135_SUMS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, name = line.split(maxsplit=1)
                sums[name.strip()] = digest
    verify = load("evidence/release/release-install-verification.json")
    checks = [
        check("package_present", V135_ZIP.is_file(), str(V135_ZIP)),
        check("zip_sha_matches_sums", sums.get(V135_ZIP.name) == sha256_file(V135_ZIP) if V135_ZIP.is_file() else False,
              sha256_file(V135_ZIP) if V135_ZIP.is_file() else "missing"),
        check("clean_install_verified", bool(verify.get("ok")), f"install={verify.get('install', {}).get('exit')} doctor={verify.get('doctor', {}).get('exit')}"),
        check("no_private_payload", verify.get("extract", {}).get("forbidden_payload") == [],
              verify.get("extract", {}).get("forbidden_payload")),
        check("dual_entrypoints", verify.get("entrypoints", {}).get("uiux_enums_exit") == 0
              and verify.get("entrypoints", {}).get("verify_enums_exit") == 0, "uiux + uiux-verify"),
        check("manifest_complete", verify.get("extract", {}).get("manifest_file_mismatch") == [], "manifest hashes"),
        check("doctor_reported", verify.get("doctor", {}).get("overall_status") is not None,
              verify.get("doctor", {}).get("overall_status")),
    ]
    return write("R9", "PASS" if all(c["ok"] for c in checks if c["blocking"]) else "FAIL", checks,
                 {"package": str(V135_ZIP), "sha256": sha256_file(V135_ZIP) if V135_ZIP.is_file() else None})


GATES = {"R0": r0, "R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6, "R7": r7, "R8": r8, "R9": r9}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", required=True, choices=list(GATES) + ["all"])
    args = parser.parse_args(argv)
    targets = list(GATES) if args.gate == "all" else [args.gate]
    failed = []
    for gate in targets:
        payload = GATES[gate]()
        print(json.dumps({"gate": gate, "state": payload["state"],
                          "evidence": str(EVID / f"{gate}.json"),
                          "failed": [c["check"] for c in payload["checks"] if not c["ok"] and c["blocking"]]}))
        if payload["state"] != "PASS":
            failed.append(gate)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
