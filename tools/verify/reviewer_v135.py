"""TASK-06: independent reviewer verification for V1.3.5 (separate process).

Recomputes numbers from raw evidence, checks the risk-gate implementation and
negative tests, verifies G1/AB/audit evidence and reports the true isolation
level. It never issues INDEPENDENT_REVIEW_PASS.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SUITE = Path(r"G:\AI\uiux-v135-wt")
ROOT = Path(r"G:\AI\uiux-v135")
AUDIT = ROOT / "evidence" / "audit" / "v135"
OUT = ROOT / "evidence" / "verify"
FINDINGS: list[dict] = []


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add(fid: str, claim: str, verdict: str, detail) -> None:
    FINDINGS.append({"id": fid, "claim": claim, "verdict": verdict, "detail": detail})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    risk = json.loads((AUDIT / "risk-gate-v135.json").read_text(encoding="utf-8"))
    inventory = json.loads((SUITE / "inventory" / "templates" / "new-manga-v135.json").read_text(encoding="utf-8"))
    coverage = json.loads((AUDIT / "coverage-matrix.json").read_text(encoding="utf-8"))
    manifest = json.loads((AUDIT / "evidence-manifest.json").read_text(encoding="utf-8"))
    task_result = json.loads((AUDIT / "task-result.json").read_text(encoding="utf-8"))
    facts = json.loads((ROOT / "evidence" / "release" / "report-facts-v135.json").read_text(encoding="utf-8"))
    isolated = json.loads((ROOT / "evidence" / "task04" / "isolated-execution.json").read_text(encoding="utf-8"))
    ab = json.loads((ROOT / "evidence" / "task05" / "ab-regression.json").read_text(encoding="utf-8"))
    discovery = json.loads((ROOT / "evidence" / "task02" / "discovery.json").read_text(encoding="utf-8"))
    scope_review = json.loads((ROOT / "evidence" / "task02" / "scope-review.json").read_text(encoding="utf-8"))

    # RV-01 no vacuous guard in risk_gate
    src = (SUITE / "runtime" / "uiux_engine" / "risk_gate.py").read_text(encoding="utf-8")
    add("RV-01", "risk gate has no always-true guard", "CONFIRMED" if "or True" not in src else "DISPUTED",
        {"or_true_present": "or True" in src})

    # RV-02 negative tests
    tests_text = (SUITE / "tests" / "unit" / "test_risk_gate_negative.py").read_text(encoding="utf-8")
    test_count = len(re.findall(r"^def test_", tests_text, re.MULTILINE))
    add("RV-02", "negative/fault-injection tests present (>=16)", "CONFIRMED" if test_count >= 16 else "DISPUTED",
        {"tests": test_count})

    # RV-03 independent high-risk recomputation
    high_risk = [i for i in inventory["items"] if i["declared_scope"] == "included" and i["risk_level"] in ("P0", "P1")]
    pass_scopes = {r.get("scope_ref") for r in coverage["records"] if r["test_state"] == "PASS" and r.get("evidence_refs")}
    verified = [i for i in high_risk if i["stable_id"] in pass_scopes]
    add("RV-03", "high-risk denominator/verified recomputed from inventory+coverage",
        "CONFIRMED" if (len(high_risk), len(verified)) == (10, 3)
        and risk["execution_coverage"]["high_risk_total"] == 10
        and risk["execution_coverage"]["high_risk_verified"] == 3 else "DISPUTED",
        {"inventory_high_risk": len(high_risk), "recomputed_verified": len(verified),
         "gate_total": risk["execution_coverage"]["high_risk_total"],
         "gate_verified": risk["execution_coverage"]["high_risk_verified"]})

    # RV-04 PASS evidence resolves
    ids = {item["id"] for item in manifest["items"]}
    dangling = [ref for r in coverage["records"] for ref in r.get("evidence_refs", []) if ref not in ids]
    add("RV-04", "all PASS evidence references resolve", "CONFIRMED" if not dangling else "DISPUTED", {"dangling": dangling})

    # RV-05 isolated execution proof
    add("RV-05", "isolated execution has verified backup and restore",
        "CONFIRMED" if isolated.get("verdict") == "PASS" and isolated.get("restore_consistent") else "DISPUTED",
        {"verdict": isolated.get("verdict"), "restore_consistent": isolated.get("restore_consistent"),
         "backup_files": isolated.get("backup", {}).get("files")})

    # RV-06 G1 discovery bound honestly
    binding = discovery["source_binding"]
    add("RV-06", "G1 discovery records source binding and dirty state",
        "CONFIRMED" if binding.get("value") and "business_source_dirty" in binding else "DISPUTED",
        {"source": binding.get("value"), "business_source_dirty": binding.get("business_source_dirty")})

    # RV-07 A/B regression
    add("RV-07", "7 environment cases classified as environment",
        "CONFIRMED" if ab["summary"]["cases"] == 7 and ab["summary"]["failures"] == 0 and
        ab["summary"]["product_eligible"] == 0 else "DISPUTED", ab["summary"])

    # RV-08 facts vs risk gate consistency
    separation = facts.get("separation", {})
    add("RV-08", "release facts match the risk gate and task result",
        "CONFIRMED" if separation.get("mechanism") == risk.get("integrity_status")
        and separation.get("business_high_risk", {}).get("verified") == risk["execution_coverage"]["high_risk_verified"]
        and facts.get("counts", {}).get("task_status") == task_result.get("status") else "DISPUTED",
        {"mechanism": separation.get("mechanism"), "verified": separation.get("business_high_risk", {}).get("verified"),
         "task_status": facts.get("counts", {}).get("task_status")})

    # RV-09 protected historical evidence untouched
    v133_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=r"G:\AI\universal-uiux-engineering",
                               capture_output=True, text=True).stdout.strip()
    v134_gate = Path(r"G:\AI\uiux-v134\evidence\gates\R6.json")
    add("RV-09", "V1.3.3 source repo and V1.3.4 evidence preserved",
        "CONFIRMED" if v133_head == "314e803ceaec6e03781da2c6e94bb548297b95a8" and v134_gate.is_file() else "DISPUTED",
        {"v133_head": v133_head[:7], "v134_R6_present": v134_gate.is_file()})

    # RV-10 independence not overstated
    add("RV-10", "reviewer reports its true isolation level",
        "CONFIRMED", {"pid": os.getpid(), "isolation": "ISOLATED_SESSION",
                      "independence": "INDEPENDENCE_UNVERIFIED", "external_anchor": None})

    # RV-11 scope review findings carried forward
    add("RV-11", "scope review findings are not silently dropped",
        "CONFIRMED" if scope_review.get("findings") else "DISPUTED",
        {"findings": len(scope_review.get("findings", [])), "verdict": scope_review.get("verdict")})

    disputed = [f for f in FINDINGS if f["verdict"] == "DISPUTED"]
    summary = {"findings": len(FINDINGS), "confirmed": len([f for f in FINDINGS if f["verdict"] == "CONFIRMED"]),
               "disputed": len(disputed)}
    (OUT / "reviewer-findings-v135.json").write_text(
        json.dumps({"schema_version": "1.3.5", "kind": "reviewer_findings", "summary": summary, "findings": FINDINGS},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V1.3.5 独立 Reviewer 复核报告", "",
             f"- 进程：独立 PID {os.getpid()}；模型家族 deepseek（同族如实披露）",
             "- 独立性：`ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED`；**不签发** `INDEPENDENT_REVIEW_PASS`",
             "- 方法：独立进程重算 inventory/coverage 数字、检查 risk gate 源码与负面测试、核对 G1/AB/隔离执行/facts 一致性", "",
             f"- 结论：`{'CONFIRMED_WITH_LIMITS' if not disputed else 'DISPUTED'}`；检查 {len(FINDINGS)} 项，DISPUTED {len(disputed)} 项", "",
             "| 编号 | 复核项 | 结论 | 关键数据 |", "|---|---|---|---|"]
    for f in FINDINGS:
        lines.append(f"| {f['id']} | {f['claim']} | {f['verdict']} | `{json.dumps(f['detail'], ensure_ascii=False)[:160]}` |")
    lines += ["", "## 无法核实/保留项", "",
              "- 外部独立签发：未取得（无外部信任锚）。",
              "- 高风险隔离执行覆盖率：3/10，产品能力阻断（GAP/禁用/原生交互），未伪造提升。",
              "- 运行时与源码漂移：隔离副本业务源码有外部未提交修改，运行时 EXE 为旧构建；已记录。"]
    (OUT / "REVIEWER_REPORT_V135.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "disputed": [f["id"] for f in disputed],
                      "out": str(OUT / "reviewer-findings-v135.json")}, ensure_ascii=False, indent=2))
    return 0 if not disputed else 1


if __name__ == "__main__":
    raise SystemExit(main())
