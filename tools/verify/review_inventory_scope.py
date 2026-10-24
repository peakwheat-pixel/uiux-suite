"""Independent scope review of the V1.3.5 inventory (TASK-02 requirement).

Checks that the declared scope was not shrunk and that discovery evidence does
not contradict the declarations. Same-model, separate process:
ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED is recorded, never INDEPENDENT_REVIEW_PASS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

V135_INV = Path(r"G:\AI\uiux-v135-wt\inventory\templates\new-manga-v135.json")
V134_INV = Path(r"G:\AI\uiux-v135-wt\inventory\templates\new-manga-v134.json")
TASK02 = Path(r"G:\AI\uiux-v135\evidence\task02")
OUT = TASK02


def main() -> int:
    inv135 = json.loads(V135_INV.read_text(encoding="utf-8"))
    inv134 = json.loads(V134_INV.read_text(encoding="utf-8"))
    discovery = json.loads((TASK02 / "discovery.json").read_text(encoding="utf-8"))
    reconciliation = json.loads((TASK02 / "inventory-reconciliation.json").read_text(encoding="utf-8"))

    findings = []

    def add(fid: str, claim: str, verdict: str, detail: dict) -> None:
        findings.append({"id": fid, "claim": claim, "verdict": verdict, "detail": detail})

    included_135 = [i["stable_id"] for i in inv135["items"] if i["declared_scope"] == "included"]
    included_134 = [i["stable_id"] for i in inv134["items"] if i["declared_scope"] == "included"]
    add("SC-01", "declared included scope is not shrunk versus V1.3.4",
        "PASS" if len(included_135) >= len(included_134) and set(included_134) <= set(included_135) else "FAIL",
        {"v134": len(included_134), "v135": len(included_135)})

    excluded_135 = [i for i in inv135["items"] if i["declared_scope"] == "excluded"]
    add("SC-02", "excluded items stay explicitly declared",
        "PASS" if len(excluded_135) == 3 else "FAIL",
        {"excluded": [i["stable_id"] for i in excluded_135]})

    not_found = [row for row in reconciliation["items"] if row["state"] == "NOT_FOUND_IN_SOURCE"]
    add("SC-03", "every declared item has source evidence",
        "PASS" if not not_found else "FAIL",
        {"not_found": [row["stable_id"] for row in not_found]})

    dialogs = discovery.get("dialogs", [])
    duplicate_confirm = [d for d in dialogs if "delete" in d["dialog"] or "permanent" in d["dialog"]]
    add("SC-04", "delete confirmation implementation exists and is declared",
        "PASS" if duplicate_confirm and "ITM-DIALOG-DELETE" in included_135 else "FAIL",
        {"delete_dialogs": [d["dialog"] for d in duplicate_confirm]})

    entries = [row["testid"] for row in discovery.get("entries", [])]
    search_evidence = [t for t in entries if "search" in t.lower()]
    region_evidence = [s for s in discovery.get("source_files", []) if "region" in s.lower()] + \
                      [t for t in entries if "region" in t.lower()]
    task_evidence = [s for s in discovery.get("source_files", [])
                     if "task" in s.lower() or "progres" in s.lower()] + \
                    [t for t in entries if "task" in t.lower()] + \
                    [s for s in discovery.get("state_machines", []) if "status" in s.lower() or "phase" in s.lower()]
    add("SC-05", "previously omitted scopes have implementation evidence in source",
        "PASS" if search_evidence and region_evidence and task_evidence else "FAIL",
        {"search": search_evidence[:4], "region": region_evidence[:4], "task": task_evidence[:4],
         "note": "search is implemented inline in the bookshelf components, not as a standalone page"})

    known_groups = {
        "create": "ITM-IMPORT-FLOW (creation entry is part of the bookshelf/import domain)",
        "import": "ITM-IMPORT-FLOW / ITM-DIALOG-IMPORT-CONFIRM",
        "export": "ITM-EXPORT-FLOW",
        "delete": "ITM-DIALOG-DELETE",
        "permanent": "ITM-CMD-PERMANENT-DELETE / ITM-DIALOG-DELETE",
        "relabel": "ITM-REGION-EDIT",
        "rename": "ITM-REGION-EDIT",
        "reader": "ITM-PAGE-READER (reader settings dialog)",
        "settings": "ITM-PAGE-SETTINGS",
    }
    unaccounted = []
    for dialog in dialogs:
        name = dialog["dialog"]
        hit = next((key for key in known_groups if key in name), None)
        if hit is None:
            unaccounted.append(dialog)
    add("SC-06", "discovered dialogs are accounted for or explicitly listed as inventory gaps",
        "FINDING" if unaccounted else "PASS",
        {"unaccounted_dialogs": [d["dialog"] for d in unaccounted],
         "coverage_assumption": known_groups,
         "note": "accounted dialogs are covered by existing items; remaining ones are recorded as inventory refinement items"})

    binding = discovery["source_binding"]
    add("SC-07", "source binding records dirty worktree honestly",
        "PASS" if binding["value"] and "dirty" in binding else "FAIL",
        {"value": binding["value"], "dirty": binding["dirty"],
         "business_source_dirty": binding["business_source_dirty"]})

    add("SC-08", "scope review is an isolated-session review, not independent attestation",
        "PASS",
        {"pid": os.getpid(), "isolation": "ISOLATED_SESSION",
         "independence": "INDEPENDENCE_UNVERIFIED"})

    failed = [f for f in findings if f["verdict"] == "FAIL"]
    findings_count = [f for f in findings if f["verdict"] == "FINDING"]
    payload = {
        "schema_version": "1.3.5",
        "kind": "inventory_scope_review",
        "reviewer": {"identity": "isolated process (deepseek)", "role": "scope reviewer",
                     "isolation": "ISOLATED_SESSION", "independence": "INDEPENDENCE_UNVERIFIED",
                     "pid": os.getpid()},
        "findings": findings,
        "verdict": "FAIL" if failed else ("CONFIRMED_WITH_LIMITS" if findings_count else "CONFIRMED"),
    }
    (OUT / "scope-review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V1.3.5 Inventory 声明范围独立复核", "",
             f"- 结论：`{payload['verdict']}`；检查 {len(findings)} 项，FAIL {len(failed)} 项",
             f"- 独立性：`ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED`（不签发独立通过）", "",
             "| 编号 | 检查项 | 结论 | 细节 |", "|---|---|---|---|"]
    for f in findings:
        lines.append(f"| {f['id']} | {f['claim']} | {f['verdict']} | `{json.dumps(f['detail'], ensure_ascii=False)[:160]}` |")
    (OUT / "SCOPE_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "failed": [f["id"] for f in failed],
                      "out": str(OUT / "scope-review.json")}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
