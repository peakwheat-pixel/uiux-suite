from __future__ import annotations

import json
from typing import Any, Callable

import pytest

from conftest import FIXTURES

from uiux_engine import geometry, rules

GEOMETRY_FIXTURES = FIXTURES / "geometry"
FIXTURE_NAMES = ("clean", "clipped-overlap", "low-contrast", "focus")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_measurement(name: str) -> dict[str, Any]:
    path = GEOMETRY_FIXTURES / f"{name}-measurement.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_ground_truth(name: str) -> dict[str, Any]:
    path = GEOMETRY_FIXTURES / f"{name}-measurement.gt.json"
    return json.loads(path.read_text(encoding="utf-8"))


def finding_keys(result: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (finding["rule_id"], finding["element_id"], finding.get("related_element_id", ""))
        for finding in result["findings"]
    }


def element(
    element_id: str = "el",
    role: str = "button",
    rect: tuple[float, float, float, float] = (0, 0, 100, 40),
    **extra: Any,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": element_id,
        "role": role,
        "rect": {"x": rect[0], "y": rect[1], "w": rect[2], "h": rect[3]},
    }
    data.update(extra)
    return data


def measurement(*elements: dict[str, Any], background: str = "#ffffff") -> dict[str, Any]:
    return {
        "viewport": {"w": 800, "h": 600},
        "background": background,
        "elements": list(elements),
    }


def rule_ids(result: dict[str, Any]) -> set[str]:
    return {finding["rule_id"] for finding in result["findings"]}


# ---------------------------------------------------------------------------
# color parsing and WCAG math
# ---------------------------------------------------------------------------


def test_parse_color_accepts_hex_and_rgb_forms():
    assert geometry.parse_color("#fff") == (255, 255, 255)
    assert geometry.parse_color("#1D4ED8") == (29, 78, 216)
    assert geometry.parse_color("rgb(29, 78, 216)") == (29, 78, 216)
    assert geometry.parse_color(" rgb( 0 ,0,0 ) ") == (0, 0, 0)


def test_parse_color_rejects_malformed_or_unopaque_values():
    for value in ("red", "#12345", "rgb(1,2)", "rgb(256,0,0)", "rgba(0,0,0,0.5)", ""):
        with pytest.raises(geometry.MeasurementError):
            geometry.parse_color(value)


def test_relative_luminance_endpoints_and_midpoint():
    assert geometry.relative_luminance("#ffffff") == pytest.approx(1.0)
    assert geometry.relative_luminance("#000000") == pytest.approx(0.0)
    assert geometry.relative_luminance("#808080") == pytest.approx(0.2158, abs=1e-4)


def test_contrast_ratio_known_values_and_symmetry():
    assert geometry.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert geometry.contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)
    assert geometry.contrast_ratio("#808080", "#ffffff") == pytest.approx(3.949, abs=1e-3)
    assert geometry.contrast_ratio("#ffffff", "#808080") == pytest.approx(
        geometry.contrast_ratio("#808080", "#ffffff")
    )


def test_large_text_classification_uses_wcag_thresholds():
    assert geometry.is_large_text(24) is True
    assert geometry.is_large_text(18.66, 700) is True
    assert geometry.is_large_text(18.66) is False
    assert geometry.is_large_text(20) is False
    assert geometry.is_large_text(20, 700) is True


# ---------------------------------------------------------------------------
# fixtures vs frozen ground truth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_fixture_matches_ground_truth(fixture_name: str):
    result = geometry.probe(load_measurement(fixture_name))
    ground_truth = load_ground_truth(fixture_name)
    expected = {
        (item["rule_id"], item["element_id"], item.get("related_element_id", ""))
        for item in ground_truth["expected_findings"]
    }
    assert finding_keys(result) == expected
    assert result["summary"]["fail"] == ground_truth["expected_fail_count"]


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_fixtures_never_claim_native_runtime(fixture_name: str):
    result = geometry.probe(load_measurement(fixture_name))
    assert result["runtime_level"] == "SIMULATED"
    assert result["mode"] == "measurement_json"
    assert result["probe_id"] == "layout_geometry_probe"


def test_clean_fixture_reports_zero_fail_and_ok():
    result = geometry.probe(load_measurement("clean"))
    assert result["ok"] is True
    assert result["runtime_level"] == "SIMULATED"
    assert result["findings"] == []
    assert result["summary"] == {
        "fail": 0,
        "warning": 0,
        "info": 0,
        "elements": 16,
        "interactive_elements": 5,
        "rules_evaluated": list(geometry.SUPPORTED_RULES),
    }


@pytest.mark.parametrize("fixture_name", ("clipped-overlap", "low-contrast", "focus"))
def test_defect_fixtures_report_fail_and_not_ok(fixture_name: str):
    result = geometry.probe(load_measurement(fixture_name))
    assert result["ok"] is False
    assert result["summary"]["fail"] == len(result["findings"])


def test_ground_truth_covers_every_supported_rule():
    covered: set[str] = set()
    for fixture_name in FIXTURE_NAMES:
        covered.update(rule_ids(geometry.probe(load_measurement(fixture_name))))
    assert covered == set(geometry.SUPPORTED_RULES)


def test_fixture_findings_only_use_frozen_catalog_rules():
    catalog = {rule["rule_id"]: rule for rule in rules.load_catalog()["rules"]}
    for fixture_name in FIXTURE_NAMES:
        result = geometry.probe(load_measurement(fixture_name))
        for finding in result["findings"]:
            assert finding["rule_id"] in catalog
            assert finding["rule_id"] in geometry.SUPPORTED_RULES
            assert finding["severity"] == catalog[finding["rule_id"]]["severity"]


# ---------------------------------------------------------------------------
# legal negatives / boundary cases
# ---------------------------------------------------------------------------


def test_contained_child_of_clipping_ancestor_is_not_flagged():
    parent = element("card", role="region", rect=(0, 0, 300, 100), overflow={"hidden": True})
    inside = element("inside", role="text", rect=(10, 10, 100, 20), text="inside")
    result = geometry.probe(measurement(parent, inside))
    assert result["findings"] == []


def test_child_escaping_clipping_ancestor_is_flagged():
    parent = element("card", role="region", rect=(0, 0, 300, 100), overflow={"hidden": True})
    escaping = element(
        "escaping", role="text", rect=(250, 10, 100, 20), text="escapes", parentId="card"
    )
    result = geometry.probe(measurement(parent, escaping))
    assert finding_keys(result) == {("UX-GEOM-001", "escaping", "")}


def test_adjacent_and_subpixel_overlapping_targets_are_not_flagged():
    first = element("first", rect=(0, 0, 100, 40), interactive=True)
    touching = element("touching", rect=(100, 0, 100, 40), interactive=True)
    rounded = element("rounded", rect=(199.75, 0, 100, 40), interactive=True)
    result = geometry.probe(measurement(first, touching, rounded))
    assert result["findings"] == []


def test_real_overlap_is_flagged_once_with_related_element():
    first = element("first", rect=(0, 0, 100, 40), interactive=True)
    second = element("second", rect=(99, 0, 100, 40), interactive=True)
    result = geometry.probe(measurement(first, second))
    assert finding_keys(result) == {("UX-GEOM-002", "first", "second")}
    assert result["findings"][0]["evidence"]["intersection"] == {
        "x": 99.0,
        "y": 0.0,
        "w": 1.0,
        "h": 40.0,
    }


def test_fully_nested_targets_are_treated_as_intentional_composition():
    outer = element("outer", role="switch", rect=(0, 0, 200, 80), interactive=True)
    inner = element("inner", rect=(10, 10, 24, 24), interactive=True)
    result = geometry.probe(measurement(outer, inner))
    assert result["findings"] == []


def test_target_size_boundary_and_non_interactive_exemption():
    too_small = element("too-small", rect=(0, 0, 23.99, 40), interactive=True)
    boundary = element("boundary", rect=(0, 100, 24, 24), interactive=True)
    decorative = element("decorative", role="icon", rect=(0, 200, 16, 16))
    result = geometry.probe(measurement(too_small, boundary, decorative))
    assert finding_keys(result) == {("UX-SPACE-002", "too-small", "")}


def test_legal_ellipsis_and_scrollable_overflow_are_suppressed():
    ellipsis = element(
        "ellipsis",
        role="text",
        rect=(0, 0, 100, 20),
        text="long text…",
        styles={"fontSize": 14, "lineHeight": 20},
        overflow={"scrollWidth": 240, "clientWidth": 100, "ellipsis": True},
    )
    scrollable = element(
        "scrollable",
        role="text",
        rect=(0, 40, 100, 20),
        text="scroll area",
        styles={"fontSize": 14, "lineHeight": 20},
        overflow={"scrollHeight": 260, "clientHeight": 20, "scrollable": True},
    )
    result = geometry.probe(measurement(ellipsis, scrollable))
    assert result["findings"] == []

    clipped = element(
        "clipped",
        role="text",
        rect=(0, 80, 100, 20),
        text="long text",
        styles={"fontSize": 14, "lineHeight": 20},
        overflow={"scrollWidth": 240, "clientWidth": 100},
    )
    clipped_result = geometry.probe(measurement(clipped))
    assert finding_keys(clipped_result) == {("UX-GEOM-001", "clipped", "")}


def test_explicit_clipped_flag_and_invisible_text_are_flagged():
    explicit = element(
        "explicit",
        role="text",
        rect=(0, 0, 100, 20),
        text="clipped",
        styles={"fontSize": 14, "lineHeight": 20},
        overflow={"clipped": True},
    )
    invisible = element("invisible", role="text", rect=(0, 40, 0, 20), text="hidden")
    short_box = element(
        "short-box",
        role="text",
        rect=(0, 80, 100, 12),
        text="too tall",
        styles={"fontSize": 14, "lineHeight": 20},
    )
    result = geometry.probe(measurement(explicit, invisible, short_box))
    assert finding_keys(result) == {
        ("UX-GEOM-001", "explicit", ""),
        ("UX-GEOM-001", "invisible", ""),
        ("UX-GEOM-001", "short-box", ""),
    }


def test_non_content_elements_are_not_clipping_targets():
    decoration = element("decoration", role="icon", rect=(0, 0, 16, 16), overflow={"clipped": True})
    result = geometry.probe(measurement(decoration))
    assert result["findings"] == []


# ---------------------------------------------------------------------------
# contrast details
# ---------------------------------------------------------------------------


def test_contrast_inherits_ancestor_background():
    card = element("card", role="region", rect=(0, 0, 300, 120), styles={"bgColor": "#f3f4f6"})
    copy = element(
        "copy",
        role="text",
        rect=(10, 10, 200, 20),
        text="inherited background",
        parentId="card",
        styles={"fontSize": 14, "lineHeight": 20, "color": "#808080"},
    )
    result = geometry.probe(measurement(card, copy))
    assert finding_keys(result) == {("UX-COLOR-001", "copy", "")}
    evidence = result["findings"][0]["evidence"]
    assert evidence["background"] == "#f3f4f6"
    assert evidence["ratio"] == pytest.approx(3.59, abs=0.01)
    assert evidence["large_text"] is False


def test_contrast_large_text_threshold_uses_font_size_and_weight():
    normal = element(
        "normal",
        role="text",
        rect=(0, 0, 200, 20),
        text="normal",
        styles={"fontSize": 20, "lineHeight": 20, "color": "#808080"},
    )
    large = element(
        "large",
        role="text",
        rect=(0, 40, 200, 36),
        text="large",
        styles={"fontSize": 32, "lineHeight": 36, "color": "#808080"},
    )
    bold = element(
        "bold",
        role="text",
        rect=(0, 90, 200, 24),
        text="bold",
        styles={"fontSize": 19, "lineHeight": 24, "color": "#808080", "fontWeight": 700},
    )
    result = geometry.probe(measurement(normal, large, bold))
    assert finding_keys(result) == {("UX-COLOR-001", "normal", "")}


def test_rgb_and_short_hex_colors_are_evaluated():
    rgb_copy = element(
        "rgb",
        role="text",
        rect=(0, 0, 200, 20),
        text="rgb",
        styles={"fontSize": 14, "lineHeight": 20, "color": "rgb(128, 128, 128)"},
    )
    hex_copy = element(
        "hex",
        role="text",
        rect=(0, 40, 200, 20),
        text="hex",
        styles={"fontSize": 14, "lineHeight": 20, "color": "#888"},
    )
    result = geometry.probe(measurement(rgb_copy, hex_copy))
    assert finding_keys(result) == {
        ("UX-COLOR-001", "hex", ""),
        ("UX-COLOR-001", "rgb", ""),
    }


# ---------------------------------------------------------------------------
# focus details
# ---------------------------------------------------------------------------


def test_focus_rule_requires_interactive_element_and_focus_information():
    non_interactive = element(
        "note", role="text", rect=(0, 0, 200, 20), text="note", styles={"focusVisible": False}
    )
    unknown_focus = element("unknown", rect=(0, 40, 100, 40), interactive=True)
    hidden_focus = element(
        "hidden", rect=(0, 90, 100, 40), interactive=True, styles={"focusVisible": False}
    )
    result = geometry.probe(measurement(non_interactive, unknown_focus, hidden_focus))
    assert finding_keys(result) == {("UX-A11Y-003", "hidden", "")}


def test_focus_ring_is_compared_with_ancestor_surface():
    surface = element(
        "surface", role="region", rect=(0, 0, 300, 120), styles={"bgColor": "#111827"}
    )
    button = element(
        "button",
        rect=(10, 10, 120, 40),
        interactive=True,
        parentId="surface",
        styles={"bgColor": "#1d4ed8", "focusVisible": True, "focusColor": "#111827"},
    )
    result = geometry.probe(measurement(surface, button))
    assert finding_keys(result) == {("UX-A11Y-003", "button", "")}
    evidence = result["findings"][0]["evidence"]
    assert evidence["background"] == "#111827"
    assert evidence["ratio"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# output contract and structural validation
# ---------------------------------------------------------------------------


def test_probe_output_contract_and_summary():
    payload = load_measurement("clipped-overlap")
    result = geometry.probe(payload)
    assert set(result) >= {"ok", "findings", "summary", "runtime_level"}
    assert result["viewport"] == {"w": 1000.0, "h": 700.0}
    summary = result["summary"]
    assert summary["fail"] == len(result["findings"])
    assert summary["warning"] == 0
    assert summary["info"] == 0
    assert summary["elements"] == len(payload["elements"])
    assert summary["interactive_elements"] == sum(
        1 for item in payload["elements"] if item.get("interactive")
    )
    for finding in result["findings"]:
        assert set(finding) >= {"rule_id", "severity", "element_id", "message"}


def test_native_claim_in_input_cannot_upgrade_evidence():
    payload = load_measurement("clean")
    payload["runtime_level"] = "NATIVE_APP"
    payload["source"] = "getBoundingClientRect"
    result = geometry.probe(payload)
    assert result["runtime_level"] == "SIMULATED"
    assert result["mode"] == "measurement_json"


def test_probe_is_deterministic_and_sorted():
    payload = load_measurement("clipped-overlap")
    first = geometry.probe(payload)
    second = geometry.probe(payload)
    assert first == second
    keys = [
        (finding["rule_id"], finding["element_id"], finding.get("related_element_id", ""))
        for finding in first["findings"]
    ]
    assert keys == sorted(keys)


def test_probe_file_matches_probe():
    path = GEOMETRY_FIXTURES / "low-contrast-measurement.json"
    assert geometry.probe_file(path) == geometry.probe(load_measurement("low-contrast"))


def test_empty_element_list_is_ok():
    result = geometry.probe({"viewport": {"w": 10, "h": 10}, "elements": []})
    assert result["ok"] is True
    assert result["findings"] == []
    assert result["summary"]["elements"] == 0


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda payload: payload.pop("viewport"), "viewport"),
        (lambda payload: payload.pop("elements"), "elements"),
        (lambda payload: payload.update(elements={"a": 1}), "must be a list"),
        (lambda payload: payload.update(viewport={"w": 0, "h": 1}), "> 0"),
        (lambda payload: payload["elements"][0].pop("role"), "role"),
        (lambda payload: payload["elements"][0].pop("rect"), "rect"),
        (
            lambda payload: payload["elements"][0].update(
                rect={"x": 0, "y": 0, "w": -1, "h": 10}
            ),
            ">= 0",
        ),
        (
            lambda payload: payload["elements"][0].update(
                rect={"x": True, "y": 0, "w": 1, "h": 1}
            ),
            "finite",
        ),
        (lambda payload: payload["elements"][0].update(styles={"colour": "#fff"}), "unknown keys"),
        (
            lambda payload: payload["elements"][0].update(styles={"color": "red"}),
            "unsupported color",
        ),
        (lambda payload: payload["elements"][0].update(overflow={"scollWidth": 1}), "unknown keys"),
        (lambda payload: payload["elements"][0].update(parentId="ghost"), "unknown element"),
        (lambda payload: payload["elements"][0].update(parentId="el"), "own parent"),
        (
            lambda payload: payload["elements"].append(dict(payload["elements"][0])),
            "duplicate element id",
        ),
        (lambda payload: payload["elements"].append(element("other", parentId="el"))
         or payload["elements"][0].update(parentId="other"), "cycle"),
    ],
)
def test_invalid_measurement_raises(mutate: Callable[[dict[str, Any]], Any], message: str):
    payload = measurement(element("el"))
    mutate(payload)
    with pytest.raises(geometry.MeasurementError, match=message):
        geometry.probe(payload)


# ---------------------------------------------------------------------------
# catalog guard
# ---------------------------------------------------------------------------


def test_supported_rules_are_frozen_catalog_rules():
    catalog = {rule["rule_id"]: rule for rule in rules.load_catalog()["rules"]}
    assert set(geometry.SUPPORTED_RULES) <= set(catalog)
    for rule_id in geometry.PROBE_OWNED_RULES:
        assert catalog[rule_id]["detector"] == geometry.PROBE_ID
    severities = geometry.catalog_severities()
    for rule_id in geometry.SUPPORTED_RULES:
        assert severities[rule_id] == catalog[rule_id]["severity"]
        assert severities[rule_id] == "FAIL"


def test_probe_never_emits_unfrozen_rule_ids():
    for fixture_name in FIXTURE_NAMES:
        result = geometry.probe(load_measurement(fixture_name))
        assert rule_ids(result) <= set(geometry.SUPPORTED_RULES)
