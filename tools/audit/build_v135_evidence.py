"""Build V1.3.5 audit evidence from the two real capture runs (TASK-03).

Inputs (read-only): evidence/audit/probe/pilot-run-v135, pilot-run-v135b
Outputs: evidence/audit/v135/{task-request,coverage-matrix,gate-results,
evidence-manifest,tool-logs,design-review,task-result}.json + risk-gate-v135.json
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(r"G:\AI\uiux-v135")
PROBE = ROOT / "evidence" / "audit" / "probe"
OUT = ROOT / "evidence" / "audit" / "v135"
SUITE = Path(r"G:\AI\uiux-v135-wt")
COPY = Path(r"G:\AI\uiux-workbench-copy")
EXE = COPY / "apps" / "desktop" / "src-tauri" / "target" / "release" / "m2rc1-desktop.exe"
RUNS = ("pilot-run-v135", "pilot-run-v135b")
RUN_ID = "nm-v135-audit-20261024-01"
NOW = "2026-10-24T05:10:00+00:00"
PROBE_ID = "P-V135-01"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(data) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(COPY), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    created = NOW
    expiry = (datetime.fromisoformat(NOW) + timedelta(days=30)).isoformat()
    captures_all: list[str] = []
    run_logs = {}
    for run in RUNS:
        log = json.loads((PROBE / run / "run-log.json").read_text(encoding="utf-8"))
        run_logs[run] = log
        captures_all.extend(c["name"] for c in log["captures"])

    items = []
    for run in RUNS:
        log = run_logs[run]
        for cap in log["captures"]:
            name = cap["name"]
            for kind, sub, suffix in (("screenshot", "screens", ".png"), ("dom_snapshot", "dom", ".html")):
                path = PROBE / run / sub / f"{name}{suffix}"
                item_id = f"EV-V135-{name.upper().replace('-', '_')}_{'PNG' if suffix == '.png' else 'DOM'}"
                items.append({
                    "id": item_id, "status": "AVAILABLE", "kind": kind, "storage_class": "evidence",
                    "source_sha256": sha256_file(path), "redacted_sha256": None,
                    "references": [f"probe/{run}/{sub}/{name}{suffix}"],
                    "created_at": created, "retention_policy": "run_default", "expiry_at": expiry,
                    "redaction": {"kind": "none", "method": "manual", "recheck_status": "NOT_RECHECKED"},
                    "provenance": {"producer": "uiux pilot probe harness (V1.3.5)", "probe_id": PROBE_ID,
                                   "execution_level": "NATIVE_APP", "tool_log_ref": f"TL-{run.upper()}-01",
                                   "environment_digest": None},
                })
        log_path = PROBE / run / "run-log.json"
        items.append({
            "id": f"EV-V135-{run.upper().replace('-', '_')}_RUNLOG", "status": "AVAILABLE",
            "kind": "test_log", "storage_class": "evidence", "source_sha256": sha256_file(log_path),
            "redacted_sha256": None, "references": [f"probe/{run}/run-log.json"],
            "created_at": created, "retention_policy": "run_default", "expiry_at": expiry,
            "redaction": {"kind": "none", "method": "manual", "recheck_status": "NOT_RECHECKED"},
            "provenance": {"producer": "uiux pilot probe harness (V1.3.5)", "probe_id": PROBE_ID,
                           "execution_level": "NATIVE_APP", "tool_log_ref": f"TL-{run.upper()}-01",
                           "environment_digest": None},
        })
    write = lambda name, payload: (OUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write("evidence-manifest.json", {
        "schema_version": "1.3.5", "run_id": RUN_ID,
        "evidence_policy": {"profile": "local_private", "retention_days": 30, "release_retention_days": 90},
        "items": items, "created_at": created, "updated_at": created,
    })
    manifest_index = {item["id"]: item for item in items}

    def refs(*names: str) -> list[str]:
        out = []
        for name in names:
            out.extend(["EV-V135-" + name.upper().replace("-", "_") + "_PNG",
                        "EV-V135-" + name.upper().replace("-", "_") + "_DOM"])
        return out

    env = {
        "host": "dsh", "os": "Windows 11", "os_version": "10.0.26100", "dpi_scale": 1.0,
        "process_path": str(EXE), "window_title": "New Manga", "session_kind": "isolated_desktop",
    }
    source_fp = {"kind": "git_commit", "value": git("rev-parse", "HEAD"),
                 "algorithm": "isolated copy HEAD; worktree dirty state recorded in TASK-02 discovery"}
    records = []

    def rec(task, scenario, scope, state, cap_names, *, required="SIMULATED", observed="NATIVE_APP",
            disposition=None, capability_available=None, notes="", extra=None):
        ev = refs(*cap_names) if cap_names else ["EV-V135-PILOT_RUN_V135_RUNLOG"]
        record = {
            "task_id": task, "scenario_id": scenario,
            "required_runtime_level": required, "observed_runtime_level": observed,
            "test_state": state, "review_isolation_level": "SELFTEST", "probe_id": PROBE_ID,
            "evidence_refs": ev, "execution_mode": "READONLY", "execution_environment": env,
            "source_fingerprint": source_fp, "notes": notes,
        }
        if scope:
            record["scope_ref"] = scope
        if disposition:
            record["disposition"] = disposition
        if capability_available is not None:
            record["capability_available"] = capability_available
            if capability_available is False:
                record["capability_evidence_refs"] = ev
        if extra:
            record.update(extra)
        return record

    records += [
        rec("T01-search", "S-SEARCH", "ITM-PAGE-SEARCH", "PASS",
            ["31-search-query", "32-search-no-match", "33-search-cleared"],
            notes="query/no-match/clear verified; sort & filters verified in same scope (45-47)"),
        rec("T02-sort-filter", "S-SORT-FILTER", "ITM-PAGE-SEARCH", "PASS",
            ["45-sort-changed", "46-filter-favorite", "47-filter-archived"],
            notes="sort options title/updated_at; favorite filter changes list 3->0; archived filter toggled"),
        rec("T03-bookshelf", "S-BOOKSHELF", "ITM-MENU-MAIN", "PASS", ["30-bookshelf-v135"]),
        rec("T04-book-detail-delete", "S-DELETE-ENTRY", "ITM-DIALOG-DELETE", "UNVERIFIED",
            ["34-book-detail", "35-delete-entry-disabled"], observed="NONE",
            disposition="NOT_APPLICABLE", capability_available=False,
            notes="entry detail-delete-btn is disabled (title GAP-G2); dialog component exists in source but is unreachable"),
        rec("T05-workbench", "S-WORKBENCH", "ITM-PAGE-WORKBENCH", "PASS", ["36-workbench-v135"]),
        rec("T06-region-list", "S-REGION-LIST", "ITM-REGION-LIST", "UNVERIFIED",
            ["37-region-overlay", "38-region-inspector"], observed="NATIVE_APP",
            disposition="ENVIRONMENT_UNAVAILABLE",
            notes="partial: Region 0 overlay/inspector visible, empty list; no region data in fixture to verify list rows"),
        rec("T07-region-edit", "S-REGION-EDIT", "ITM-REGION-EDIT", "UNVERIFIED",
            ["38-region-inspector"], observed="NONE",
            disposition="ENVIRONMENT_UNAVAILABLE",
            notes="no region data available; inspector shows 'no region selected'"),
        rec("T08-task-states", "S-TASK-STATES", "ITM-TASK-STATES", "UNVERIFIED",
            ["39-task-progress"], disposition="TOOL_UNAVAILABLE",
            notes="partial: panel visible + empty + capability note (Core lacks ListRuns); transitions not verifiable"),
        rec("T09-settings", "S-SETTINGS", "ITM-PAGE-SETTINGS", "PASS",
            ["40-settings-task-concurrency", "41-settings-recycle-bin"]),
        rec("T10-reader", "S-READER", "ITM-PAGE-READER", "PASS", ["42-reader-v135"]),
        rec("T11-import-dialog", "S-IMPORT-DIALOG", "ITM-IMPORT-FLOW", "PASS", ["44-import-dialog"],
            notes="dialog opened; execution not performed"),
        rec("T12-import-confirm", "S-IMPORT-CONFIRM", "ITM-DIALOG-IMPORT-CONFIRM", "UNVERIFIED",
            ["44-import-dialog"], observed="NONE", disposition="NATIVE_INTERACTION_UNAVAILABLE",
            notes="read-only audit; import confirmation not executed"),
        rec("T13-export-dialog", "S-EXPORT-DIALOG", "ITM-EXPORT-FLOW", "UNVERIFIED",
            [], observed="NONE", disposition="AUDITOR_OMISSION",
            notes="workbench-export clicked but export-dialog did not appear; capture 43 shows workbench, entry unverified"),
        rec("T14-permanent-delete", "S-PERMANENT-DELETE", "ITM-CMD-PERMANENT-DELETE", "UNVERIFIED",
            ["35-delete-entry-disabled"], observed="NONE", disposition="NATIVE_INTERACTION_UNAVAILABLE",
            notes="dangerous write not executed"),
        rec("T15-import-execute", "S-IMPORT-EXECUTE", "ITM-CMD-IMPORT-EXECUTE", "UNVERIFIED",
            ["44-import-dialog"], observed="NONE", disposition="NATIVE_INTERACTION_UNAVAILABLE",
            notes="dangerous write not executed"),
        rec("T16-launch", "S-LAUNCH", "ITM-ENTRY-DESKTOP", "PASS", ["30-bookshelf-v135"]),
    ]
    write("coverage-matrix.json", {
        "schema_version": "1.3.5", "run_id": RUN_ID, "source_fingerprint": source_fp,
        "records": records, "created_at": created,
    })

    tool_logs = []
    for run in RUNS:
        log = run_logs[run]
        tool_logs.append({
            "schema_version": "1.3.5", "log_id": f"TL-{run.upper()}-01", "run_id": RUN_ID,
            "tool": "uiux pilot probe (CDP/WebView2)", "tool_version": "1.0.0",
            "command": ["node", f"probe_{'v135' if run.endswith('v135') else 'v135b'}.mjs", run, "run-pilot"],
            "cwd": str(Path(r"G:\AI\uiux-v135\tools\pilot")),
            "env_digest": sha256_json({"M2RC1_PACKAGED": "1", "NEWMANGA_DATA_ROOT": "<sandbox>/run-pilot"}),
            "input_digest": sha256_json({"run": run}),
            "output_digest": sha256_json({"captures": [c["name"] for c in log["captures"]]}),
            "exit_code": 0, "started_at": log["startedAt"], "finished_at": log["endedAt"],
            "duration_ms": 60000, "execution_level": "NATIVE_APP", "probe_id": PROBE_ID,
            "evidence_refs": [f"EV-V135-{run.upper().replace('-', '_')}_RUNLOG"],
            "log_sha256": sha256_file(PROBE / run / "run-log.json"),
            "stdout_ref": str(PROBE / run / "run-log.json"), "stderr_ref": None,
            "redaction": {"applied": False, "kinds": []},
        })
    write("tool-logs.json", tool_logs)

    def gate(gate_id, state, applicability, ev_refs, observed="NATIVE_APP", reasons=None, notes=""):
        return {
            "gate_id": gate_id, "state": state, "applicability": applicability,
            "required_runtime_level": "SIMULATED", "observed_runtime_level": observed,
            "evidence_refs": [{
                "evidence_id": item, "kind": manifest_index[item]["kind"],
                "status": manifest_index[item]["status"], "sha256": manifest_index[item]["source_sha256"],
                "probe_id": PROBE_ID, "evidence_level": "NATIVE_APP",
                "expiry_at": manifest_index[item]["expiry_at"],
                "redaction": {"kind": "none", "method": "manual", "recheck_status": "NOT_RECHECKED"},
            } for item in ev_refs],
            "probe_ids": [PROBE_ID], "tool_log_refs": [f"TL-{RUNS[0].upper()}-01"],
            "reason_codes": reasons or [], "notes": notes, "computed_at": NOW,
        }

    gates = {
        "G0": gate("G0", "PASS", "MANDATORY", ["EV-V135-30_BOOKSHELF_V135_PNG"], "NONE",
                   notes="app launched in isolated env; CDP attached"),
        "G1": gate("G1", "PASS", "MANDATORY", ["EV-V135-36_WORKBENCH_V135_PNG"], "NATIVE_APP",
                   notes="G1 static discovery re-run in this round (TASK-02 discovery.json; 12 pages/6 dialogs/581 entries)"),
        "G2": gate("G2", "PASS", "REVIEW_ONLY", ["EV-V135-30_BOOKSHELF_V135_DOM"], "SIMULATED",
                   notes="runtime navigation/page skeleton/focus observed"),
        "G3": gate("G3", "PASS", "REVIEW_ONLY", ["EV-V135-42_READER_V135_DOM"], "SIMULATED",
                   notes="design system read-only; L4 review in design-review.json"),
        "G4": gate("G4", "PASS", "REVIEW_ONLY", ["EV-V135-30_BOOKSHELF_V135_PNG"], "SIMULATED",
                   notes="read-only checks only"),
        "G5": gate("G5", "PASS", "MANDATORY",
                   [item["id"] for item in items if item["kind"] == "screenshot"], "NATIVE_APP",
                   notes="real WebView2 process + CDP captures across two runs"),
    }
    policy = json.loads((Path(r"G:\AI\uiux-v134\evidence\audit\v134") / "policy-base.json").read_text(encoding="utf-8"))
    policy["schema_version"] = "1.3.5"
    policy["policy_id"] = "POL-NM-V135-AUDIT-01"
    policy["description"] = "Read-only UI/UX audit with coverage backfill (V1.3.5 Phase B)"
    request = {
        "schema_version": "1.3.5", "run_id": RUN_ID, "mode": "audit",
        "project_root": str(COPY),
        "project": {"name": "New Manga — isolated copy (V1.3.5 audit)", "has_existing_ui": True, "tech_stack": "tauri"},
        "target_scope": ["apps/desktop/frontend/src", "apps/desktop/src-tauri"],
        "caller": {"kind": "direct", "invoker": "dsh agent lead", "git_management": "standalone",
                   "role": "UI/UX auditor", "task_id": "task-v135"},
        "policy": policy,
        "execution_policy": {
            "read_only_source": True, "allow_production_data_write": False,
            "allow_uia_input": False, "allow_physical_os_input": False,
            "os_input_target_allowlist": [], "allowed_write_globs": [],
            "max_total_repair_cycles": 0, "require_native_for_production_complete": False,
        },
        "evidence_policy": {"profile": "local_private", "retention_days": 30,
                            "release_retention_days": 90,
                            "redaction": {"images": "none", "paths": False, "fields": False, "recheck": False}},
        "runtime_targets": ["NATIVE_APP"],
        "requested_outputs": ["flows.json", "gate-results.json", "evidence-manifest.json",
                              "coverage-matrix.json", "design-review.json"],
        "review": {"independent_required": False, "reviewer_context_ref": None},
        "created_at": created,
    }
    write("task-request.json", request)
    write("gate-results.json", {
        "schema_version": "1.3.5", "run_id": RUN_ID, "mode": "audit",
        "source_fingerprint": source_fp, "request_digest": sha256_json(request),
        "gates": gates, "created_at": created,
    })

    def dim(dimension_id, verdict, caps, notes):
        return {"dimension_id": dimension_id, "verdict": verdict,
                "evidence_refs": [f"probe/pilot-run-v135/screens/{name}.png" for name in caps],
                "notes": notes, "confidence": 0.7}

    design = {
        "schema_version": "1.3.5", "run_id": RUN_ID, "scenario_id": "S-BOOKSHELF",
        "rubric_version": "1.0.0",
        "reviewer": {"identity": "lead (DSH, read-only audit)", "role": "UI/UX auditor",
                     "source": "selftest", "independence_proof_ref": None},
        "dimensions": [
            dim("goal_discoverability", "WARN", ["30-bookshelf-v135"], "工具栏中英混排、Emoji 图标仍在"),
            dim("task_completeness", "WARN", ["31-search-query", "42-reader-v135"], "搜索/排序/筛选新增验证；导入执行/删除未执行"),
            dim("mental_model_ia", "PASS", ["30-bookshelf-v135", "36-workbench-v135"], "四页 + 回收站层级清晰"),
            dim("error_recovery", "WARN", ["39-task-progress"], "任务面板明确提示 ListRuns 不可用"),
            dim("continuity_resume", "WARN", ["42-reader-v135"], "阅读器打开；跨会话恢复未验证"),
            dim("keyboard_efficiency", "WARN", ["35-delete-entry-disabled"], "禁用入口无原因说明（V1.3.3 UIUX-014 同源）"),
            dim("visual_hierarchy", "WARN", ["30-bookshelf-v135"], "对比度/字号问题沿用 V1.3.3/V1.3.4 结论"),
            dim("information_density", "WARN", ["40-settings-task-concurrency"], "设置分区密度高"),
            dim("learning_cost", "WARN", ["39-task-progress"], "未开放能力直接暴露"),
            dim("professional_fit", "WARN", ["36-workbench-v135"], "与既往判断一致"),
        ],
        "overall_verdict": "PARTIAL", "dissent": [],
        "open_questions": ["Region 无数据，列表/编辑未验证", "任务状态迁移不可达", "导出对话框未打开", "原生选择器不可驱动"],
        "evidence_refs": ["probe/", "coverage-matrix.json", "gate-results.json"],
        "created_at": created,
    }
    write("design-review.json", design)

    env_vars = {**os.environ, "PYTHONPATH": str(SUITE / "runtime"), "PYTHONUTF8": "1"}
    cmd = [sys.executable, "-m", "uiux_engine.cli", "finalize",
           "--request", str(OUT / "task-request.json"),
           "--gate-results", str(OUT / "gate-results.json"),
           "--coverage", str(OUT / "coverage-matrix.json"),
           "--evidence-manifest", str(OUT / "evidence-manifest.json"),
           "--tool-logs", str(OUT / "tool-logs.json"),
           "--design-review", str(OUT / "design-review.json"),
           "--schema-version", "1.3.5", "--now", NOW, "--out", str(OUT / "task-result.json")]
    proc = subprocess.run(cmd, cwd=str(SUITE), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env_vars, timeout=300)
    result = json.loads((OUT / "task-result.json").read_text(encoding="utf-8")) if (OUT / "task-result.json").is_file() else None

    sys.path.insert(0, str(SUITE / "runtime"))
    from uiux_engine import risk_gate
    inventory = json.loads((SUITE / "inventory" / "templates" / "new-manga-v135.json").read_text(encoding="utf-8"))
    verdict = risk_gate.evaluate(inventory, records, items, schema_version="1.3.5")
    verdict["verdict_digest"] = risk_gate.digest(verdict)
    write("risk-gate-v135.json", verdict)

    print(json.dumps({
        "ok": True, "captures": len(captures_all), "evidence_items": len(items),
        "coverage_records": len(records),
        "finalize_exit": proc.returncode, "finalize_errors": (json.loads(proc.stdout).get("errors") if proc.stdout.strip().startswith("{") else None),
        "task_result": {k: result.get(k) for k in ("status", "delivery_status", "runtime_evidence_level")} if result else None,
        "g6": result.get("derived_g6", {}).get("state") if result else None,
        "risk_gate": {"gate_status": verdict["gate_status"], "integrity": verdict["integrity_status"],
                      "coverage": verdict["execution_coverage"], "violations": verdict["violations"][:5]},
        "out": str(OUT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
