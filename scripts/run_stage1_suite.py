"""T1.7: run all Stage 1 detectors over frozen fixtures and build a confusion matrix.

Only SIMULATED static detectors are in scope here. Hard-rule false negatives or
false positives (severity FAIL) fail the suite; WARNING mismatches are recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "qa"
GT_ROOT = REPO_ROOT / "tests" / "fixtures" / "ground_truth"
FLOW_ROOT = REPO_ROOT / "tests" / "fixtures" / "flows"
GEOMETRY_ROOT = REPO_ROOT / "tests" / "fixtures" / "geometry"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rule_severity() -> dict[str, str]:
    catalog = _load(REPO_ROOT / "knowledge" / "rules" / "catalog.v1.0.json")
    return {rule["rule_id"]: rule["severity"] for rule in catalog["rules"]}


def collect_style() -> list[dict]:
    from uiux_engine import style_linter

    samples = []
    for annotation_path in sorted((GT_ROOT / "annotations").glob("*.json")):
        annotation = _load(annotation_path)
        fixture = GT_ROOT / annotation["fixture"]
        result = style_linter.lint_file(fixture, root=GT_ROOT, stack=annotation["stack"])
        expected = sorted(item["rule_id"] for item in annotation["expected"])
        actual = sorted(finding["rule_id"] for finding in result["findings"])
        samples.append(
            {
                "sample_id": f"style:{annotation['fixture']}",
                "expected": expected,
                "actual": actual,
            }
        )
    return samples


def collect_flows() -> list[dict]:
    from uiux_engine import flow_validator

    gt = _load(FLOW_ROOT / "gt.json")
    samples = []
    for name, expected in gt.items():
        report = flow_validator.validate(_load(FLOW_ROOT / name))
        samples.append(
            {
                "sample_id": f"flows:{name}",
                "expected": sorted(expected["expected_rules"]),
                "actual": sorted({finding["rule_id"] for finding in report["findings"]}),
            }
        )
    return samples


def collect_geometry() -> list[dict]:
    from uiux_engine import geometry

    samples = []
    for gt_path in sorted(GEOMETRY_ROOT.glob("*.gt.json")):
        gt = _load(gt_path)
        report = geometry.probe(_load(GEOMETRY_ROOT / gt["measurement"]))
        expected = sorted(item["rule_id"] for item in gt["expected_findings"])
        actual = sorted(finding["rule_id"] for finding in report["findings"] if finding["severity"] == "FAIL")
        samples.append(
            {
                "sample_id": f"geometry:{gt['measurement']}",
                "expected": expected,
                "actual": actual,
            }
        )
    return samples


def classify(samples: list[dict], severities: dict[str, str]) -> dict:
    matrix = Counter()
    per_rule: dict[str, Counter] = defaultdict(Counter)
    rows = []
    hard_failures: list[dict] = []
    for sample in samples:
        expected = Counter(sample["expected"])
        actual = Counter(sample["actual"])
        tp = sum((expected & actual).values())
        fn_list = list((expected - actual).elements())
        fp_list = list((actual - expected).elements())
        matrix["tp"] += tp
        matrix["fn"] += len(fn_list)
        matrix["fp"] += len(fp_list)
        if not expected and not actual:
            matrix["tn"] += 1
            status = "TN"
        elif fn_list and fp_list:
            status = "PARTIAL"
        elif fn_list:
            status = "FN"
        elif fp_list:
            status = "FP"
        else:
            status = "TP"
        rows.append({"sample_id": sample["sample_id"], "expected": sample["expected"], "actual": sample["actual"], "status": status})
        for rule_id in expected:
            if rule_id in actual:
                per_rule[rule_id]["tp"] += 1
            else:
                per_rule[rule_id]["fn"] += 1
                if severities.get(rule_id) == "FAIL":
                    hard_failures.append({"sample_id": sample["sample_id"], "rule_id": rule_id, "kind": "FN"})
        for rule_id in actual:
            if rule_id not in expected:
                per_rule[rule_id]["fp"] += 1
                if severities.get(rule_id) == "FAIL":
                    hard_failures.append({"sample_id": sample["sample_id"], "rule_id": rule_id, "kind": "FP"})
        if status == "TN":
            pass
    return {
        "matrix": {key: matrix[key] for key in ("tp", "fp", "tn", "fn")},
        "per_rule": [
            {"rule_id": rule_id, **{key: per_rule[rule_id][key] for key in ("tp", "fp", "tn", "fn")}}
            for rule_id in sorted(per_rule)
        ],
        "samples": rows,
        "hard_failures": hard_failures,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYTHONPATH", str(REPO_ROOT / "runtime"))
    severities = _rule_severity()
    samples = collect_style() + collect_flows() + collect_geometry()
    result = classify(samples, severities)
    report = {
        "schema_version": "1.3.3",
        "suite": "stage1-detectors",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8"
        ).stdout.strip(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix": result["matrix"],
        "per_rule": result["per_rule"],
        "samples": result["samples"],
    }
    from uiux_engine import contracts

    problems = contracts.validation_errors("confusion-matrix", report)
    (OUT_DIR / "confusion-matrix.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "ok": not problems and not result["hard_failures"],
        "samples": len(samples),
        "matrix": result["matrix"],
        "hard_failures": result["hard_failures"],
        "schema_errors": problems,
        "evidence": "qa/confusion-matrix.json",
        "inputs_sha256": {
            "catalog": sha256_file(REPO_ROOT / "knowledge" / "rules" / "catalog.v1.0.json"),
            "style_fixtures": sha256_file(GT_ROOT / "annotations" / "qt-positive-contrast.json"),
            "flows_gt": sha256_file(FLOW_ROOT / "gt.json"),
            "geometry_gt": sha256_file(GEOMETRY_ROOT / "clean-measurement.gt.json"),
        },
    }
    (OUT_DIR / "stage1-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
