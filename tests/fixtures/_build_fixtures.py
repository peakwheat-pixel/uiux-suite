"""Generate V1.3.3 contract fixtures (deterministic).

Run:
    python tests/fixtures/_build_fixtures.py

The script writes valid/invalid/semantic-invalid instances and a finalize
scenario. All hashes are computed from logical content with the same
canonicalization the engine uses, so fixtures stay consistent with the runtime.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = FIXTURE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "runtime"))

from uiux_engine import contracts, gates  # noqa: E402

CREATED = "2026-10-23T12:00:00+00:00"
EXPIRY = "2027-10-23T12:00:00+00:00"
FP = {"kind": "git_commit", "value": "a" * 40, "algorithm": "git-sha1"}
PROBE_LEVELS = {
    "P-G0": "NONE",
    "P-G1": "NATIVE_APP",
    "P-G2": "NATIVE_APP",
    "P-G3": "NONE",
    "P-G4": "NONE",
    "P-G5": "NATIVE_APP",
}
EVIDENCE_KINDS = {
    "EV-G0": "tool_log",
    "EV-G1": "screenshot",
    "EV-G2": "coverage_matrix",
    "EV-G3": "tool_log",
    "EV-G4": "diff",
    "EV-G5": "test_log",
}


def sha(text: str) -> str:
    return contracts.sha256_text(text)


def write(relative: str, data: object) -> Path:
    path = FIXTURE_ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_policy(*, read_only: bool, mode: str) -> dict:
    authorization = None
    if not read_only:
        authorization = {
            "granted_by": "fixture-author",
            "granted_at": CREATED,
            "expires_at": None,
            "scopes": ["production_write"],
            "evidence_ref": "EV-AUTH",
        }
    return {
        "schema_version": "1.3.3",
        "policy_id": "POL-FIXTURE-001",
        "description": "fixture policy",
        "roots": {
            "read_roots": ["G:/fixtures/demo/src"],
            "report_write_root": "G:/fixtures/demo/.uiux/evidence",
            "sandbox_write_root": "C:/Temp/uiux-sandbox",
            "install_write_root": "C:/Users/test/.agents/uiux-suite",
            "source_write_scope": {
                "allowed_globs": [] if read_only else ["src/ui/**"],
                "denied_globs": ["src/backend/**"],
            },
        },
        "permissions": {
            "allow_network": False,
            "allow_external_commands": ["python", "npm"],
            "deny_external_commands": ["curl", "wget"],
            "os_input": {
                "uia_patterns": True,
                "physical": False,
                "target_allowlist": [],
            },
            "max_repair_cycles": 2,
        },
        "authorization": authorization,
        "git": {"management": "standalone", "snapshot_policy": "git_commit"},
        "evidence": {
            "profile": "local_private",
            "retention_days": 30,
            "release_retention_days": 180,
        },
        "allowed_modes": [mode],
        "created_at": CREATED,
    }


def make_request(mode: str, *, read_only: bool) -> dict:
    return {
        "schema_version": "1.3.3",
        "run_id": "UIUX-20261023-001",
        "mode": mode,
        "project_root": "G:/fixtures/demo",
        "project": {"name": "fixture-demo", "has_existing_ui": True, "tech_stack": "tauri"},
        "target_scope": ["src/ui/**"],
        "caller": {"kind": "direct", "invoker": "dsh", "git_management": "standalone"},
        "policy": make_policy(read_only=read_only, mode=mode),
        "execution_policy": {
            "read_only_source": read_only,
            "allow_production_data_write": False,
            "allow_uia_input": True,
            "allow_physical_os_input": False,
            "os_input_target_allowlist": [],
            "allowed_write_globs": [] if read_only else ["src/ui/**"],
            "max_total_repair_cycles": 2,
            "require_native_for_production_complete": not read_only,
        },
        "evidence_policy": {
            "profile": "local_private",
            "retention_days": 30,
            "release_retention_days": 180,
            "redaction": {"images": "blur", "paths": True, "fields": False, "recheck": True},
        },
        "runtime_targets": ["SIMULATED"] if read_only else ["SIMULATED", "NATIVE_APP"],
        "requested_outputs": ["flows.json", "gate-results.json", "evidence-manifest.json", "design-review.json"],
        "review": {"independent_required": not read_only, "reviewer_context_ref": "ctx-reviewer-001"},
        "created_at": CREATED,
    }


def make_evidence_manifest() -> dict:
    items = []
    for evidence_id, kind in EVIDENCE_KINDS.items():
        probe_id = "P-" + evidence_id.split("-")[1]
        level = PROBE_LEVELS[probe_id]
        items.append(
            {
                "id": evidence_id,
                "status": "AVAILABLE",
                "kind": kind,
                "storage_class": "vault" if kind in ("screenshot", "dom_snapshot", "uia_tree") else "evidence",
                "source_sha256": sha("source:" + evidence_id),
                "redacted_sha256": sha("redacted:" + evidence_id),
                "references": ["tests/fixtures/scenarios/complete-redesign/" + evidence_id.lower() + ".json"],
                "created_at": CREATED,
                "retention_policy": "release_audit",
                "expiry_at": EXPIRY,
                "redaction": {
                    "kind": "path" if kind in ("tool_log", "test_log", "diff") else "image",
                    "method": "automated",
                    "recheck_status": "PASS",
                },
                "provenance": {
                    "producer": "uiux-engine",
                    "probe_id": probe_id,
                    "execution_level": level,
                    "tool_log_ref": "TL-" + evidence_id.split("-")[1],
                    "environment_digest": sha("env"),
                },
            }
        )
    return {
        "schema_version": "1.3.3",
        "run_id": "UIUX-20261023-001",
        "evidence_policy": {"profile": "local_private", "retention_days": 30, "release_retention_days": 180},
        "items": items,
        "created_at": CREATED,
        "updated_at": CREATED,
    }


def make_evidence_ref(evidence_id: str) -> dict:
    probe_id = "P-" + evidence_id.split("-")[1]
    return {
        "evidence_id": evidence_id,
        "kind": EVIDENCE_KINDS[evidence_id],
        "status": "AVAILABLE",
        "sha256": sha("source:" + evidence_id),
        "probe_id": probe_id,
        "evidence_level": PROBE_LEVELS[probe_id],
        "expiry_at": EXPIRY,
        "redaction": {"kind": "path", "method": "automated", "recheck_status": "PASS"},
    }


def make_gate_results() -> dict:
    gate_ids = [f"G{i}" for i in range(6)]
    gate_states = {
        "G0": "PASS",
        "G1": "PASS",
        "G2": "PASS",
        "G3": "PASS",
        "G4": "PASS",
        "G5": "PASS",
    }
    return {
        "schema_version": "1.3.3",
        "run_id": "UIUX-20261023-001",
        "mode": "redesign",
        "source_fingerprint": FP,
        "gates": {
            gate: {
                "gate_id": gate,
                "state": gate_states[gate],
                "applicability": "MANDATORY",
                "required_runtime_level": PROBE_LEVELS["P-" + gate],
                "observed_runtime_level": PROBE_LEVELS["P-" + gate],
                "evidence_refs": [make_evidence_ref("EV-" + gate)],
                "probe_ids": ["P-" + gate],
                "tool_log_refs": ["TL-" + gate],
                "reason_codes": [],
                "computed_at": CREATED,
            }
            for gate in gate_ids
        },
        "created_at": CREATED,
    }


def make_tool_logs() -> list[dict]:
    logs = []
    for index, (probe_id, level) in enumerate(PROBE_LEVELS.items()):
        evidence_id = "EV-" + probe_id.split("-")[1]
        logs.append(
            {
                "schema_version": "1.3.3",
                "log_id": "TL-" + probe_id.split("-")[1],
                "run_id": "UIUX-20261023-001",
                "tool": "uiux-probe",
                "tool_version": "1.3.3",
                "command": ["uiux-probe", "run", probe_id],
                "cwd": "G:/fixtures/demo",
                "env_digest": sha("env"),
                "input_digest": sha("input:" + probe_id),
                "output_digest": sha("output:" + probe_id),
                "exit_code": 0,
                "started_at": CREATED,
                "finished_at": CREATED,
                "duration_ms": 1000 + index,
                "execution_level": level,
                "probe_id": probe_id,
                "evidence_refs": [evidence_id],
                "log_sha256": sha("log:" + probe_id),
                "stdout_ref": None,
                "stderr_ref": None,
                "redaction": {"applied": True, "kinds": ["path"]},
            }
        )
    return logs


def make_coverage() -> dict:
    records = []
    for task_id, scenario in (("import", "native-import"), ("export", "native-export")):
        records.append(
            {
                "task_id": task_id,
                "scenario_id": scenario,
                "required_runtime_level": "NATIVE_APP",
                "observed_runtime_level": "NATIVE_APP",
                "test_state": "PASS",
                "review_isolation_level": "SELFTEST",
                "probe_id": "P-G5",
                "evidence_refs": ["EV-G5"],
                "execution_environment": {
                    "host": "dsh",
                    "os": "Windows 11",
                    "session_kind": "shared_desktop",
                },
                "source_fingerprint": FP,
            }
        )
    return {
        "schema_version": "1.3.3",
        "run_id": "UIUX-20261023-001",
        "source_fingerprint": FP,
        "records": records,
        "created_at": CREATED,
    }


def make_design_review() -> dict:
    dimensions = [
        "goal_discoverability",
        "task_completeness",
        "mental_model_ia",
        "error_recovery",
        "continuity_resume",
        "keyboard_efficiency",
        "visual_hierarchy",
        "information_density",
        "learning_cost",
        "professional_fit",
    ]
    return {
        "schema_version": "1.3.3",
        "run_id": "UIUX-20261023-001",
        "scenario_id": "redesign-import-panel",
        "rubric_version": "1.0",
        "reviewer": {
            "identity": "independent-reviewer-01",
            "role": "UX expert reviewer",
            "source": "independent_agent",
            "independence_proof_ref": "ATTEST-REVIEW-001",
        },
        "dimensions": [
            {
                "dimension_id": dimension,
                "verdict": "PASS",
                "evidence_refs": ["EV-G1"],
                "notes": f"{dimension}: evidence-backed pass",
                "confidence": 0.9,
            }
            for dimension in dimensions
        ],
        "overall_verdict": "PASS",
        "dissent": [],
        "open_questions": [],
        "evidence_refs": ["EV-G1", "EV-G5"],
        "created_at": CREATED,
    }


def make_attestation(manifest: dict) -> dict:
    return {
        "schema_version": "1.3.3",
        "run_id": "UIUX-20261023-001",
        "reviewed_head": FP["value"],
        "source_fingerprint": FP,
        "builder_context_ref": "ctx-builder-001",
        "reviewer_context_ref": "ctx-reviewer-001",
        "review_origin": {
            "host": "dsh",
            "launched_by": "independent-review-launcher",
            "verified_identity": "reviewer-agent-01",
            "trust_source": "host_verified",
        },
        "isolation_level": "INDEPENDENT_AGENT",
        "read_only_proof": {"enforced": True, "method": "sandbox", "evidence_ref": "EV-G0"},
        "tool_digest": sha("tool"),
        "evidence_manifest_hash": contracts.sha256_json(manifest),
        "source_unchanged": True,
        "verdict": "PASS",
        "dissent": [],
        "reviewed_at": CREATED,
    }


def make_suite_link() -> dict:
    return {
        "schema_version": "1.3.3",
        "suite_id": "universal-uiux-engineering",
        "active_version": "1.3.3",
        "path_kind": "relative_to_skill_root",
        "suite_root": "../../uiux-suite/versions/1.3.3",
        "manifest_relpath": "RELEASE_MANIFEST.json",
        "python_exe": None,
        "created_by_installer": True,
        "created_at": CREATED,
        "install_record_relpath": None,
    }


def make_release_manifest() -> dict:
    files = [
        ("runtime/uiux_engine/cli.py", "runtime"),
        ("contracts/task-request.v1.3.3.schema.json", "schema"),
        ("skills/uiux/SKILL.md", "skill"),
        ("skills/uiux/scripts/launch.py", "launcher"),
        ("LICENSE", "license"),
    ]
    return {
        "schema_version": "1.3.3",
        "suite_version": "1.3.3",
        "generated_at": CREATED,
        "builder": "fixture-builder",
        "target_platform": {"os": "windows-11", "python": "3.12.14", "node": "20.11.1"},
        "normalization": {"path_separator": "/", "case_policy": "casefolded_windows", "eol_normalized": False},
        "files": [
            {"path": path, "sha256": sha("file:" + path), "size": 100, "role": role}
            for path, role in files
        ],
        "excluded_patterns": ["**/__pycache__/**", "**/*.pyc", ".venv/**"],
        "include_launcher": True,
        "include_schemas": True,
        "include_licenses": True,
        "bundle_sha256": sha("bundle"),
    }


def make_flows() -> dict:
    return {
        "schema_version": "1.3.3",
        "view_id": "import-panel",
        "view_archetype": "desktop_workbench",
        "capabilities": {
            "async_load": True,
            "collection_display": True,
            "user_mutation": False,
            "long_running_task": True,
            "destructive_operations": False,
            "canvas_rendering": False,
        },
        "capability_evidence": [
            {
                "capability": "async_load",
                "source": {"kind": "file", "ref": "src/ui/import/ImportPanel.tsx", "locator": "useEffect"},
                "discovery": "static",
                "confidence": 0.9,
            },
            {
                "capability": "long_running_task",
                "source": {"kind": "runtime", "ref": "import_progress"},
                "discovery": "runtime",
                "confidence": 0.8,
            },
            {
                "capability": "collection_display",
                "source": {"kind": "file", "ref": "src/ui/import/ImportPanel.tsx"},
                "discovery": "static",
                "confidence": 0.7,
            },
        ],
        "tasks": [
            {
                "task_id": "import-folder",
                "actor_goal": "选择本地目录并导入图库",
                "entry_point": "toolbar.import",
                "steps": ["open-dialog", "select-folder", "confirm", "wait-progress", "review-result"],
                "states": ["empty", "loading", "ready", "error", "progress", "cancelled"],
                "runtime_assertions": [
                    {
                        "assertion_id": "import-dialog-opens",
                        "description": "导入对话框可打开",
                        "expected_states": ["ready"],
                        "probe_id": "P-G5",
                    }
                ],
                "destructive_operations": [],
            }
        ],
        "ui_anchors": [{"semantic_id": "import.progress", "testid": "import-progress"}],
    }


def make_host_capability() -> dict:
    return {
        "schema_version": "1.3.3",
        "host": "dsh",
        "host_version": "1.0.0",
        "os": "Windows 11 23H2",
        "python": "3.12.14",
        "node": None,
        "skill_roots": [
            {"path": "G:/fixtures/demo/.agents/skills", "rank": 200, "source": "project-agents", "exists": True},
            {"path": "C:/Users/test/.agents/skills", "rank": 500, "source": "user-agents", "exists": True},
        ],
        "entries": [
            {
                "name": "uiux",
                "root": "C:/Users/test/.agents/skills/uiux",
                "rank": 500,
                "shadowed_by": None,
            }
        ],
        "capabilities": {
            "skill_discovery": "READY",
            "script_exec": "READY",
            "gui_access": "READY",
            "mcp": "UNVERIFIED",
            "file_permissions": "READY",
            "resume": "UNVERIFIED",
        },
        "checks": [
            {"id": "python", "status": "READY", "detail": "Python 3.12.14 on PATH"},
            {"id": "gui", "status": "READY", "detail": "interactive desktop available"},
        ],
        "doctor_version": "1.3.3",
        "overall_status": "READY",
        "checked_at": CREATED,
    }


def build() -> dict:
    request = make_request("redesign", read_only=False)
    audit_request = make_request("audit", read_only=True)
    manifest = make_evidence_manifest()
    gate_results = make_gate_results()
    coverage = make_coverage()
    tool_logs = make_tool_logs()
    design_review = make_design_review()
    attestation = make_attestation(manifest)

    write("contracts/valid/task-request-redesign.json", request)
    write("contracts/valid/task-request-audit.json", audit_request)
    write("contracts/valid/policy.json", request["policy"])
    write("contracts/valid/gate-results.json", gate_results)
    write("contracts/valid/coverage-matrix.json", coverage)
    write("contracts/valid/evidence-manifest.json", manifest)
    write("contracts/valid/tool-log.json", tool_logs[0])
    write("contracts/valid/design-review.json", design_review)
    write("contracts/valid/review-attestation.json", attestation)
    write("contracts/valid/suite-link.json", make_suite_link())
    write("contracts/valid/release-manifest.json", make_release_manifest())
    write("contracts/valid/flows.json", make_flows())
    write("contracts/valid/host-capability.json", make_host_capability())

    scenario = "scenarios/complete-redesign"
    write(scenario + "/request.json", request)
    write(scenario + "/gate-results.json", gate_results)
    write(scenario + "/coverage.json", coverage)
    write(scenario + "/evidence-manifest.json", manifest)
    write(scenario + "/tool-logs.json", tool_logs)
    write(scenario + "/design-review.json", design_review)
    write(scenario + "/review-attestation.json", attestation)

    result = {
        "schema_version": "1.3.3",
        "run_id": request["run_id"],
        "mode": request["mode"],
        "status": "COMPLETE",
        "delivery_status": "INDEPENDENT_VERIFIED",
        "independent_review_status": "INDEPENDENT_REVIEW_PASS",
        "design_review_status": "PASS",
        "source_fingerprint": FP,
        "runtime_evidence_level": "NATIVE_APP",
        "review_isolation_level": "INDEPENDENT_AGENT",
        "gates": gate_results["gates"],
        "derived_g6": {
            "state": "PASS",
            "checks": [{"id": "fixture", "state": "PASS", "detail": "fixture-consistency"}],
            "computed_at": CREATED,
        },
        "coverage_matrix": coverage["records"],
        "unverified_paths": [],
        "blocking_reasons": [],
        "warn_reviews": [],
        "evidence_manifest": scenario + "/evidence-manifest.json",
        "design_review_ref": scenario + "/design-review.json",
        "review_attestation_ref": scenario + "/review-attestation.json",
        "repair_cycles": 0,
        "created_at": CREATED,
    }
    write("contracts/valid/task-result.json", result)

    # ---- invalid schema fixtures -------------------------------------------------
    bad_mode = copy.deepcopy(request)
    bad_mode["mode"] = "audit-v2"
    write("contracts/invalid/task-request-bad-mode.json", bad_mode)

    bad_scope = copy.deepcopy(request)
    bad_scope["target_scope"] = ["/absolute/path"]
    write("contracts/invalid/task-request-absolute-scope.json", bad_scope)

    warn_gate = copy.deepcopy(gate_results)
    warn_gate["gates"]["G5"]["state"] = "WARNING"
    write("contracts/invalid/gate-results-warning-token.json", warn_gate)

    g6_input = copy.deepcopy(gate_results)
    g6_input["gates"]["G6"] = copy.deepcopy(g6_input["gates"]["G0"])
    write("contracts/invalid/gate-results-with-g6.json", g6_input)

    complete_with_blockers = copy.deepcopy(result)
    complete_with_blockers["blocking_reasons"] = [
        {"gate": "G5", "code": "MISSING_EVIDENCE", "detail": "native run missing"}
    ]
    write("contracts/invalid/task-result-complete-with-blockers.json", complete_with_blockers)

    independent_no_ref = copy.deepcopy(result)
    independent_no_ref["review_attestation_ref"] = None
    write("contracts/invalid/task-result-independent-no-attestation.json", independent_no_ref)

    available_no_hash = copy.deepcopy(manifest)
    available_no_hash["items"][0]["source_sha256"] = None
    write("contracts/invalid/evidence-available-no-hash.json", available_no_hash)

    redacted_no_hash = copy.deepcopy(manifest)
    redacted_no_hash["items"][0]["status"] = "REDACTED_ONLY"
    redacted_no_hash["items"][0]["redacted_sha256"] = None
    write("contracts/invalid/evidence-redacted-no-hash.json", redacted_no_hash)

    weak_trust = copy.deepcopy(attestation)
    weak_trust["review_origin"]["trust_source"] = "user_attested"
    write("contracts/invalid/review-attestation-independent-user-attested.json", weak_trust)

    nine_dimensions = copy.deepcopy(design_review)
    nine_dimensions["dimensions"] = nine_dimensions["dimensions"][:9]
    write("contracts/invalid/design-review-nine-dim.json", nine_dimensions)

    bad_link = make_suite_link()
    bad_link["suite_root"] = "C:/agents/uiux-suite/1.3.3"
    write("contracts/invalid/suite-link-relative-absolute.json", bad_link)

    upper_hash = make_release_manifest()
    upper_hash["bundle_sha256"] = upper_hash["bundle_sha256"].upper()
    write("contracts/invalid/release-manifest-uppercase-hash.json", upper_hash)

    missing_probe = copy.deepcopy(tool_logs[0])
    del missing_probe["probe_id"]
    write("contracts/invalid/tool-log-missing-probe.json", missing_probe)

    bad_archetype = make_flows()
    bad_archetype["view_archetype"] = "mobile_page"
    write("contracts/invalid/flows-bad-archetype.json", bad_archetype)

    # ---- semantic-invalid fixtures (schema-valid, policy violations) ------------
    readonly_writes = copy.deepcopy(audit_request)
    readonly_writes["execution_policy"]["allowed_write_globs"] = ["src/**"]
    readonly_writes["policy"]["roots"]["source_write_scope"]["allowed_globs"] = ["src/**"]
    write("contracts/semantic-invalid/task-request-readonly-with-writes.json", readonly_writes)

    physical_no_auth = copy.deepcopy(request)
    physical_no_auth["execution_policy"]["allow_physical_os_input"] = True
    physical_no_auth["execution_policy"]["os_input_target_allowlist"] = ["demo.exe"]
    physical_no_auth["policy"]["permissions"]["os_input"]["physical"] = True
    physical_no_auth["policy"]["authorization"] = None
    write("contracts/semantic-invalid/task-request-physical-input-no-auth.json", physical_no_auth)

    missing_native = copy.deepcopy(request)
    missing_native["runtime_targets"] = ["SIMULATED"]
    write("contracts/semantic-invalid/task-request-missing-native-target.json", missing_native)

    scope_not_subset = copy.deepcopy(request)
    scope_not_subset["policy"]["roots"]["source_write_scope"]["allowed_globs"] = ["src/**"]
    write("contracts/semantic-invalid/task-request-write-scope-not-subset.json", scope_not_subset)

    overlap_roots = copy.deepcopy(request)
    overlap_roots["policy"]["roots"]["sandbox_write_root"] = overlap_roots["policy"]["roots"]["report_write_root"]
    write("contracts/semantic-invalid/task-request-overlap-roots.json", overlap_roots)

    return {
        "valid": 13,
        "invalid": 14,
        "semantic_invalid": 5,
        "scenario": scenario,
        "manifest_hash": contracts.sha256_json(manifest),
        "result_status": result["status"],
    }


if __name__ == "__main__":
    summary = build()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
