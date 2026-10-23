from __future__ import annotations

import copy
import json
from pathlib import Path

from uiux_engine import options

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "options"


def load() -> dict:
    return json.loads((FIXTURES / "options.json").read_text(encoding="utf-8"))


def test_valid_record_and_ranking():
    report = options.evaluate(load())
    assert report["ok"] is True
    assert report["ranking"][0]["option_id"] == "table"
    assert report["selected_option_id"] == "table"
    assert report["selected_score"] is not None


def test_weights_are_complete():
    total = sum(options.WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9
    assert set(options.WEIGHTS) == {"usability", "visual", "feasibility", "risk", "accessibility"}


def test_selected_not_top_warns_but_passes():
    record = load()
    record["selected_option_id"] = "cards"
    report = options.evaluate(record)
    assert report["ok"] is True
    assert any("not the highest" in warning for warning in report["warnings"])


def test_unknown_selected_is_rejected():
    record = load()
    record["selected_option_id"] = "ghost"
    report = options.evaluate(record)
    assert report["ok"] is False
    assert any("not an option" in error for error in report["errors"])


def test_duplicate_option_is_rejected():
    record = load()
    record["options"].append(copy.deepcopy(record["options"][0]))
    report = options.evaluate(record)
    assert report["ok"] is False
    assert any("duplicate" in error for error in report["errors"])


def test_low_accessibility_warns():
    record = load()
    record["options"][0]["scores"]["accessibility"] = 1
    report = options.evaluate(copy.deepcopy(record))
    assert any("accessibility" in warning for warning in report["warnings"])


def test_schema_invalid_is_rejected():
    record = load()
    record["options"] = record["options"][:1]
    report = options.evaluate(record)
    assert report["ok"] is False
    assert report["errors"]


def test_rationale_required():
    record = load()
    record["rationale"] = "short"
    report = options.evaluate(record)
    assert report["ok"] is False
