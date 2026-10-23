"""Design-option comparison and decision checks (T2.7)."""
from __future__ import annotations

from typing import Any

from . import contracts

WEIGHTS = {
    "usability": 0.25,
    "visual": 0.15,
    "feasibility": 0.20,
    "risk": 0.15,
    "accessibility": 0.25,
}


def evaluate(record: dict[str, Any]) -> dict[str, Any]:
    errors = contracts.validation_errors("design-options", record)
    warnings: list[str] = []
    ranking: list[dict[str, Any]] = []
    if not errors:
        option_ids = [option["option_id"] for option in record["options"]]
        if len(option_ids) != len(set(option_ids)):
            errors.append("duplicate option_id")
        if record["selected_option_id"] not in option_ids:
            errors.append(f"selected_option_id {record['selected_option_id']} is not an option")
        for option in record["options"]:
            score = round(sum(option["scores"][key] * weight for key, weight in WEIGHTS.items()), 3)
            ranking.append({"option_id": option["option_id"], "name": option["name"], "weighted_score": score})
        ranking.sort(key=lambda item: (-item["weighted_score"], item["option_id"]))
        if ranking and record["selected_option_id"] != ranking[0]["option_id"]:
            warnings.append(
                f"selected {record['selected_option_id']} is not the highest weighted option ({ranking[0]['option_id']})"
            )
        for option in record["options"]:
            if option["scores"]["accessibility"] <= 2:
                warnings.append(f"{option['option_id']}: accessibility score <= 2")
            if option["scores"]["risk"] <= 2:
                warnings.append(f"{option['option_id']}: risk-control score <= 2")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "ranking": ranking,
        "selected_option_id": record.get("selected_option_id"),
        "selected_score": next(
            (item["weighted_score"] for item in ranking if item["option_id"] == record.get("selected_option_id")),
            None,
        ),
    }
