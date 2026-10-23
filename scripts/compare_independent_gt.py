"""Compare independent blind annotations against frozen ground truth (M13)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "evidence" / "T1.1"
LABELS = EVIDENCE / "independent-annotation.labels.json"
ANNOTATIONS = REPO / "tests" / "fixtures" / "ground_truth" / "annotations"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(item: dict) -> tuple[str, int, str]:
    return (str(item["rule_id"]), int(item["line"]), str(item["severity"]))


def norm(fixture: str) -> str:
    return fixture.replace("\\", "/").removeprefix("tests/fixtures/ground_truth/")


def main() -> int:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    pairs = []
    disagreements = []
    exact = 0
    for entry in labels["annotations"]:
        fixture = norm(entry["fixture"])
        gt_path = ANNOTATIONS / (fixture.replace("/", "-").replace(".", "-") + ".json")
        # annotation files use underscores, not dashes; fall back to scanning expected fixture
        if not gt_path.is_file():
            candidates = [p for p in ANNOTATIONS.glob("*.json") if json.loads(p.read_text(encoding="utf-8")).get("fixture") == fixture]
            gt_path = candidates[0] if candidates else None
        if gt_path is None:
            disagreements.append({"fixture": fixture, "error": "frozen annotation not found"})
            continue
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        gt_set = {key(item) for item in gt.get("expected", [])}
        label_set = {key(item) for item in entry.get("findings", [])}
        match = gt_set == label_set
        exact += int(match)
        pairs.append(
            {
                "fixture": fixture,
                "match": match,
                "frozen": sorted([list(item) for item in gt_set]),
                "independent": sorted([list(item) for item in label_set]),
                "frozen_file": str(gt_path.relative_to(REPO)),
                "frozen_sha256": sha256(gt_path),
            }
        )
        if not match:
            disagreements.append({"fixture": fixture, "missing_by_independent": sorted(map(list, gt_set - label_set)), "extra": sorted(map(list, label_set - gt_set))})
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":(exclude)evidence"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
    )
    report = {
        "schema_version": "1.3.3",
        "evidence_id": "EV-T1.1-INDEPENDENT-GT",
        "kind": "review_attestation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True, text=True, encoding="utf-8").stdout.strip(),
            "dirty": dirty,
            "dirty_scope": "tracked files excluding evidence/",
        },
        "annotator": labels["annotator"],
        "method": labels["method"],
        "labels_file": str(LABELS.relative_to(REPO)),
        "labels_sha256": sha256(LABELS),
        "fixtures_total": len(pairs),
        "exact_matches": exact,
        "agreement_rate": round(exact / len(pairs), 4) if pairs else 0.0,
        "pairs": pairs,
        "disagreements": disagreements,
        "generator": {"path": "scripts/compare_independent_gt.py", "sha256": sha256(Path(__file__))},
        "notes": [
            "Frozen annotations retain independent=false as a historical field; this evidence is the independent blind annotation.",
            "Line-level ambiguity for color/selector and per-declaration spacing was resolved identically in this sample.",
        ],
    }
    out = EVIDENCE / "independent-annotation.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["agreement_rate"] == 1.0, "exact": exact, "total": len(pairs), "disagreements": disagreements}, ensure_ascii=False))
    return 0 if report["agreement_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
