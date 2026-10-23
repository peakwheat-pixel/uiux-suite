from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT

from uiux_engine import rules, style_linter
from uiux_engine.evidence import parse_time

GROUND_TRUTH = REPO_ROOT / "tests" / "fixtures" / "ground_truth"
ANNOTATIONS_DIR = GROUND_TRUTH / "annotations"
FROZEN_NOW = parse_time("2026-10-24T00:00:00+00:00")


def _load_annotations() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(ANNOTATIONS_DIR.glob("*.json"))]


ANNOTATIONS = _load_annotations()
ANNOTATION_IDS = [annotation["fixture"] for annotation in ANNOTATIONS]


def _expected_pairs(annotation: dict) -> list[tuple[str, int]]:
    return sorted((entry["rule_id"], entry["line"]) for entry in annotation["expected"])


def _actual_pairs(result: dict) -> list[tuple[str, int]]:
    return sorted((finding["rule_id"], finding["line"]) for finding in result["findings"])


def _catalog_severity() -> dict[str, str]:
    return {rule["rule_id"]: rule["severity"] for rule in rules.load_catalog()["rules"]}


@pytest.fixture(scope="module")
def catalog_severity() -> dict[str, str]:
    return _catalog_severity()


def _lint_fixture(annotation: dict, **kwargs) -> dict:
    return style_linter.lint_file(GROUND_TRUTH / annotation["fixture"], root=REPO_ROOT, **kwargs)


def _warning_exemption(**overrides) -> dict:
    exemption = {
        "rule_id": "UX-SPACE-001",
        "scope": "tests/fixtures/ground_truth/web/positive/spacing.css",
        "reason": "legacy layout frozen until Q2 migration",
        "owner": "design-system",
        "approved_by": "lead",
        "created_at": "2026-10-01T00:00:00+00:00",
        "expires_at": "2027-01-01T00:00:00+00:00",
        "ticket": "UX-123",
    }
    exemption.update(overrides)
    return exemption


# ---------------------------------------------------------------------------
# T1.1 frozen ground truth
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("annotation", ANNOTATIONS, ids=ANNOTATION_IDS)
def test_fixture_matches_frozen_ground_truth(annotation: dict, catalog_severity: dict[str, str]):
    fixture = GROUND_TRUTH / annotation["fixture"]
    assert fixture.is_file(), annotation["fixture"]
    assert annotation["schema_version"] == "uiux.style-ground-truth.v1"
    result = _lint_fixture(annotation)
    assert _actual_pairs(result) == _expected_pairs(annotation), style_linter.dump_result(result)
    for entry in annotation["expected"]:
        assert catalog_severity[entry["rule_id"]] == entry["severity"]
    for finding in result["findings"]:
        assert finding["severity"] == catalog_severity[finding["rule_id"]]


def test_all_expected_findings_reference_catalog_rule_ids(catalog_severity: dict[str, str]):
    for annotation in ANNOTATIONS:
        fixture = GROUND_TRUTH / annotation["fixture"]
        line_count = len(fixture.read_text(encoding="utf-8").splitlines())
        for entry in annotation["expected"]:
            assert entry["rule_id"] in catalog_severity
            assert entry["severity"] == catalog_severity[entry["rule_id"]]
            assert 1 <= entry["line"] <= line_count


def test_positive_fixtures_have_seeded_findings():
    positives = [annotation for annotation in ANNOTATIONS if annotation["case_kind"] == "positive"]
    assert positives
    for annotation in positives:
        assert annotation["expected"], annotation["fixture"]


def test_negative_fixtures_are_clean():
    negatives = [annotation for annotation in ANNOTATIONS if annotation["case_kind"] == "negative"]
    assert len(negatives) >= 4
    for annotation in negatives:
        result = _lint_fixture(annotation)
        assert result["findings"] == []
        assert result["ok"] is True
        assert result["summary"] == {"fail": 0, "warning": 0, "info": 0}


def test_qt_has_at_least_two_positive_and_two_negative_fixtures():
    qt = [annotation for annotation in ANNOTATIONS if annotation["stack"] == "qt"]
    assert len([annotation for annotation in qt if annotation["case_kind"] == "positive"]) >= 2
    assert len([annotation for annotation in qt if annotation["case_kind"] == "negative"]) >= 2
    assert {annotation["fixture"].split("/")[-1].split(".")[-1] for annotation in qt} == {"qss"}


def test_every_supported_rule_is_covered_by_ground_truth():
    covered = {entry["rule_id"] for annotation in ANNOTATIONS for entry in annotation["expected"]}
    required = {
        "UX-COLOR-001",
        "UX-COLOR-002",
        "UX-TYPE-001",
        "UX-TYPE-002",
        "UX-SPACE-001",
        "UX-A11Y-001",
        "UX-A11Y-003",
        "UX-A11Y-004",
        "UX-COPY-001",
        "UX-MOTION-001",
    }
    assert required <= covered
    assert set(style_linter.SUPPORTED_RULE_IDS) == required


# ---------------------------------------------------------------------------
# T1.2 result contract
# ---------------------------------------------------------------------------
def test_rule_bindings_are_frozen_catalog_only():
    assert style_linter.catalog_bindings() == []
    frozen = {rule["rule_id"] for rule in rules.load_catalog()["rules"]}
    assert set(style_linter.SUPPORTED_RULE_IDS) <= frozen


def test_result_shape_summary_and_ok_semantics():
    result = _lint_fixture(next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/a11y.html"))
    assert {"ok", "findings", "summary", "exemptions_applied"} <= set(result)
    assert result["detector"] == "style_token_linter"
    assert result["catalog_version"] == rules.load_catalog()["catalog_version"]
    assert result["ok"] is False
    assert result["summary"] == {"fail": 1, "warning": 2, "info": 0}
    for finding in result["findings"]:
        assert {"rule_id", "severity", "file", "line", "message"} <= set(finding)
        assert finding["file"] == "tests/fixtures/ground_truth/web/positive/a11y.html"


def test_warning_only_result_is_ok_and_fail_result_is_not():
    warning_only = _lint_fixture(next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/typography.css"))
    assert warning_only["summary"]["warning"] > 0
    assert warning_only["summary"]["fail"] == 0
    assert warning_only["ok"] is True
    failing = _lint_fixture(next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/contrast.css"))
    assert failing["summary"]["fail"] == 1
    assert failing["ok"] is False


def test_output_is_sorted_and_deterministic():
    annotation = next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/spacing.css")
    first = _lint_fixture(annotation)
    second = _lint_fixture(annotation)
    assert first == second
    assert style_linter.dump_result(first) == style_linter.dump_result(second)
    text = style_linter.dump_result(first)
    assert text.endswith("\n")
    assert json.loads(text) == first
    keys = [(finding["file"], finding["line"], finding["rule_id"]) for finding in first["findings"]]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Exemptions: only valid, in-scope WARNING exemptions may suppress findings
# ---------------------------------------------------------------------------
def test_warning_exemption_suppresses_and_is_audited():
    annotation = next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/spacing.css")
    baseline = _lint_fixture(annotation)
    assert len(baseline["findings"]) == 3

    exemption = _warning_exemption()
    result = _lint_fixture(annotation, exemptions=[exemption], now=FROZEN_NOW)
    assert result["findings"] == []
    assert result["summary"] == {"fail": 0, "warning": 0, "info": 0}
    assert len(result["exemptions_applied"]) == 1
    audit = result["exemptions_applied"][0]
    assert audit["status"] == "applied"
    assert audit["rule_id"] == "UX-SPACE-001"
    assert audit["approved_by"] == "lead"
    assert audit["expires_at"] == "2027-01-01T00:00:00+00:00"
    assert audit["suppressed_count"] == 3
    assert [entry["line"] for entry in audit["suppressed"]] == [2, 3, 4]
    assert audit["problems"] == []


def test_expired_exemption_is_audited_but_not_applied():
    annotation = next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/spacing.css")
    exemption = _warning_exemption(expires_at="2026-01-01T00:00:00+00:00")
    result = _lint_fixture(annotation, exemptions=[exemption], now=FROZEN_NOW)
    assert len(result["findings"]) == 3
    audit = result["exemptions_applied"][0]
    assert audit["status"] == "rejected"
    assert any("expired" in problem for problem in audit["problems"])


def test_unknown_rule_exemption_is_audited_but_not_applied():
    annotation = next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/spacing.css")
    exemption = _warning_exemption(rule_id="UX-NOPE-999")
    result = _lint_fixture(annotation, exemptions=[exemption], now=FROZEN_NOW)
    assert len(result["findings"]) == 3
    audit = result["exemptions_applied"][0]
    assert audit["status"] == "rejected"
    assert any("unknown rule_id" in problem for problem in audit["problems"])


def test_fail_severity_findings_cannot_be_exempted():
    annotation = next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/contrast.css")
    exemption = _warning_exemption(
        rule_id="UX-COLOR-001",
        scope="tests/fixtures/ground_truth/web/positive/contrast.css",
    )
    result = _lint_fixture(annotation, exemptions=[exemption], now=FROZEN_NOW)
    assert len(result["findings"]) == 1
    audit = result["exemptions_applied"][0]
    assert audit["status"] == "rejected"
    assert any("only WARNING" in problem for problem in audit["problems"])


def test_out_of_scope_exemption_is_audited_as_unused():
    annotation = next(a for a in ANNOTATIONS if a["fixture"] == "web/positive/spacing.css")
    exemption = _warning_exemption(scope="tests/fixtures/ground_truth/qt/**")
    result = _lint_fixture(annotation, exemptions=[exemption], now=FROZEN_NOW)
    assert len(result["findings"]) == 3
    audit = result["exemptions_applied"][0]
    assert audit["status"] == "unused"
    assert audit["suppressed_count"] == 0


def test_scope_glob_supports_recursive_patterns():
    nested = "tests/fixtures/ground_truth/web/positive/spacing.css"
    assert style_linter._scope_matches(nested, "tests/fixtures/ground_truth/web/**")
    assert style_linter._scope_matches(nested, "**/spacing.css")
    assert not style_linter._scope_matches(nested, "tests/fixtures/ground_truth/qt/**")
    assert style_linter._scope_matches(nested, "tests/fixtures/ground_truth/web/positive/*.css")


# ---------------------------------------------------------------------------
# Input modes
# ---------------------------------------------------------------------------
def test_infers_stack_from_suffix():
    assert style_linter.infer_stack("widgets/main.qss") == "qt"
    assert style_linter.infer_stack("src/app.css") == "web"
    assert style_linter.infer_stack("src/page.html") == "web"


def test_qss_text_is_supported():
    result = style_linter.lint_text(
        "QLabel {\n    font-size: 10px;\n}\n",
        file="widget.qss",
        stack="qt",
    )
    assert _actual_pairs(result) == [("UX-TYPE-001", 2)]


def test_html_inline_style_fragment_is_scanned():
    result = style_linter.lint_text(
        '<p style="padding: 13px;">note</p>\n',
        file="fragment.html",
        stack="web",
    )
    assert _actual_pairs(result) == [("UX-SPACE-001", 1)]


def test_tsx_style_object_is_scanned():
    result = style_linter.lint_text(
        "export const Card = () => (\n"
        "  <div style={{ padding: '13px', fontSize: '11px' }} />\n"
        ");\n",
        file="card.tsx",
        stack="web",
    )
    assert _actual_pairs(result) == [("UX-SPACE-001", 2), ("UX-TYPE-001", 2)]


def test_unknown_stack_is_rejected():
    with pytest.raises(ValueError):
        style_linter.lint_text(".a { padding: 3px; }", file="x.css", stack="winui")


def test_lint_files_aggregates_and_applies_exemptions_once():
    files = [
        GROUND_TRUTH / "web/positive/spacing.css",
        GROUND_TRUTH / "web/positive/contrast.css",
    ]
    baseline = style_linter.lint_files(files, root=REPO_ROOT)
    assert baseline["summary"] == {"fail": 1, "warning": 3, "info": 0}
    assert len(baseline["files_checked"]) == 2

    result = style_linter.lint_files(files, root=REPO_ROOT, exemptions=[_warning_exemption()], now=FROZEN_NOW)
    assert result["summary"] == {"fail": 1, "warning": 0, "info": 0}
    assert len(result["exemptions_applied"]) == 1
    assert result["exemptions_applied"][0]["suppressed_count"] == 3
