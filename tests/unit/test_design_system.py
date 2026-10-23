from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT

from uiux_engine import contracts, design_system, rules

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "design_system"
MANIFEST_PATH = FIXTURES / "cases.v1.0.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]
CASE_IDS = [case["file"] for case in CASES]

TOKENS = design_system.load_tokens()
FREEZE = contracts.load_json(design_system.FREEZE_PATH)
CATALOG = rules.load_catalog()
CATALOG_SEVERITY = {rule["rule_id"]: rule["severity"] for rule in CATALOG["rules"]}
TOKEN_INDEX = {record["token"]: record for record in design_system.token_index(TOKENS)}


def _entry_id(entry: dict) -> str:
    return str(entry.get("rule_id") or entry.get("dimension"))


def _pairs(entries) -> list[tuple[str, int]]:
    return sorted((_entry_id(entry), int(entry["line"])) for entry in entries)


def _finding_pairs(result: dict) -> list[tuple[str, int]]:
    return _pairs(result["findings"])


def _lint_case(case: dict) -> dict:
    return design_system.lint_file(FIXTURES / case["file"], root=REPO_ROOT)


def _line_count(case: dict) -> int:
    return len((FIXTURES / case["file"]).read_text(encoding="utf-8").splitlines())


# ---------------------------------------------------------------------------
# T2.3 token document, freeze record and aliases
# ---------------------------------------------------------------------------
def test_tokens_document_is_schema_valid():
    assert design_system.token_schema_errors(TOKENS) == []
    assert contracts.validation_errors("design-tokens", TOKENS) == []
    for key in ("schema_version", "token_set_version", "theme", "colors", "spacing", "typography"):
        assert key in TOKENS
    assert TOKENS["schema_version"] == "1.3.3"
    assert TOKENS["token_set_version"] == "1.0"
    assert TOKENS["theme"] == "both"


def test_tokens_cover_required_scales_and_cjk_font_stack():
    assert len(TOKENS["colors"]) >= 10
    assert len(TOKENS["spacing"]) >= 5
    assert len(TOKENS["typography"]) >= 4
    assert len(TOKENS["radii"]) >= 2
    assert len(TOKENS["motion"]) >= 2
    spacing = {design_system._token_length_px(value) for value in TOKENS["spacing"].values()}
    assert {4.0, 8.0, 16.0} <= spacing
    for style in TOKENS["typography"].values():
        assert {"fontSize", "lineHeight"} <= set(style)
        assert style["fontSize"] >= 12
        assert style["lineHeight"] >= 1.2
    families = " ".join(style["fontFamily"] for style in TOKENS["typography"].values())
    # m3: CJK coverage comes from system font stacks only; no bundled font files.
    assert "Microsoft YaHei" in families or "PingFang SC" in families
    assert not list(design_system.TOKENS_DIR.glob("*.ttf")) + list(design_system.TOKENS_DIR.glob("*.otf"))


def test_freeze_record_matches_token_digest_and_counts():
    assert design_system.verify_frozen() == []
    record = design_system.freeze_record(TOKENS)
    assert FREEZE["token_set_version"] == record["token_set_version"]
    assert FREEZE["theme"] == record["theme"]
    assert FREEZE["counts"] == record["counts"]
    assert FREEZE["sha256"] == record["sha256"]
    assert len(FREEZE["sha256"]) == 64
    assert FREEZE["source"] == "self-authored"
    assert FREEZE["license"] == "internal"
    assert "system fonts only" in FREEZE["font_policy"]


def test_freeze_detects_tampered_digest(tmp_path: Path):
    tampered = dict(FREEZE)
    tampered["sha256"] = "0" * 64
    freeze_path = tmp_path / "tokens.v1.0.freeze.json"
    freeze_path.write_text(json.dumps(tampered), encoding="utf-8")
    problems = design_system.verify_frozen(freeze_path)
    assert problems
    assert any("sha256" in problem for problem in problems)


def test_token_semantics_are_clean():
    assert design_system.semantic_problems(TOKENS) == []
    assert design_system.semantic_problems() == []


def test_alias_tokens_resolve_to_palette_values():
    primary = TOKEN_INDEX["color-text-primary"]
    assert primary["alias"] is True
    assert primary["resolved"] is True
    assert primary["css_var"] == "--color-text-primary"
    assert primary["value"] == "#1f2328"
    assert TOKEN_INDEX["color-accent"]["value"] == "#0969da"
    assert TOKEN_INDEX["color-bg-canvas"]["value"] == "#ffffff"
    assert TOKEN_INDEX["space-3"]["value"] == "12px"
    assert TOKEN_INDEX["body.fontSize"]["value"] == "14px"
    # alias targets are palette literals, not further unresolved var() chains
    assert "var(" not in primary["value"]


def test_alias_cycle_and_unresolved_alias_are_rejected():
    cyclic = copy.deepcopy(TOKENS)
    cyclic["colors"]["color-text-primary"] = "var(--color-text-secondary)"
    cyclic["colors"]["color-text-secondary"] = "var(--color-text-primary)"
    problems = design_system.semantic_problems(cyclic)
    assert problems
    assert any("alias" in problem for problem in problems)

    dangling = copy.deepcopy(TOKENS)
    dangling["colors"]["color-text-primary"] = "var(--color-missing)"
    dangling_problems = design_system.semantic_problems(dangling)
    assert any("unresolved token alias" in problem for problem in dangling_problems)


# ---------------------------------------------------------------------------
# Catalog binding: Rule ID only when frozen, otherwise WARNING dimension
# ---------------------------------------------------------------------------
def test_catalog_bindings_are_frozen_only():
    assert design_system.catalog_bindings() == []
    assert set(design_system.SUPPORTED_RULE_IDS) <= set(CATALOG_SEVERITY)
    assert set(design_system.DIMENSIONS) == {"color_token", "font_size_token", "line_height_token"}
    for rule in design_system.supported_rules():
        assert rule["severity"] in ("FAIL", "WARNING", "INFO")
        assert rule["severity"] == CATALOG_SEVERITY[rule["rule_id"]]


def test_every_finding_is_mapped_or_dimensioned_with_catalog_severity():
    seen_ids: set[str] = set()
    seen_dimensions: set[str] = set()
    for case in CASES:
        for finding in _lint_case(case)["findings"]:
            seen_ids.add(finding.get("rule_id") or finding.get("dimension"))
            has_rule = "rule_id" in finding
            has_dimension = "dimension" in finding
            assert has_rule != has_dimension
            if has_rule:
                assert finding["rule_id"] in design_system.SUPPORTED_RULE_IDS
                assert finding["severity"] == CATALOG_SEVERITY[finding["rule_id"]]
            else:
                assert finding["dimension"] in design_system.DIMENSIONS
                assert finding["severity"] == "WARNING"
                seen_dimensions.add(finding["dimension"])
            assert finding["token"] in design_system.TOKEN_NAMESPACES
    assert set(design_system.SUPPORTED_RULE_IDS) <= seen_ids
    assert seen_dimensions == set(design_system.DIMENSIONS)
    assert "UX-SPACE-001" in seen_ids
    assert "UX-TYPE-001" in seen_ids
    assert "UX-TYPE-002" in seen_ids
    assert "UX-MOTION-001" in seen_ids


# ---------------------------------------------------------------------------
# Frozen fixtures: compliant samples clean, violating samples not missed
# ---------------------------------------------------------------------------
def test_manifest_declares_both_case_kinds_with_valid_expectations():
    assert MANIFEST["schema_version"] == "uiux.design-system-fixtures.v1"
    assert MANIFEST["token_set_version"] == TOKENS["token_set_version"]
    compliant = [case for case in CASES if case["case_kind"] == "compliant"]
    violations = [case for case in CASES if case["case_kind"] == "violation"]
    assert len(compliant) >= 3
    assert len(violations) >= 3
    assert len({case["file"] for case in CASES}) == len(CASES)
    for case in compliant:
        assert case["expected"] == []
    for case in violations:
        assert case["expected"]
        for entry in case["expected"]:
            identifier = _entry_id(entry)
            assert identifier in CATALOG_SEVERITY or identifier in design_system.DIMENSIONS
            assert 1 <= entry["line"] <= _line_count(case)


@pytest.mark.parametrize("case", [case for case in CASES if case["case_kind"] == "compliant"], ids=[
    case["file"] for case in CASES if case["case_kind"] == "compliant"
])
def test_compliant_fixtures_have_zero_deviations(case: dict):
    result = _lint_case(case)
    assert result["findings"] == [], design_system.dump_result(result)
    assert result["ok"] is True
    assert result["summary"] == {"fail": 0, "warning": 0, "info": 0}


@pytest.mark.parametrize("case", [case for case in CASES if case["case_kind"] == "violation"], ids=[
    case["file"] for case in CASES if case["case_kind"] == "violation"
])
def test_violation_fixtures_match_expected_without_misses(case: dict):
    result = _lint_case(case)
    assert _finding_pairs(result) == _pairs(case["expected"]), design_system.dump_result(result)
    assert result["ok"] is False
    assert result["summary"]["fail"] == 0
    assert result["summary"]["warning"] == len(result["findings"])


def test_finding_shape_and_line_numbers():
    checked = 0
    for case in CASES:
        result = _lint_case(case)
        line_count = _line_count(case)
        for finding in result["findings"]:
            checked += 1
            for key in ("file", "line", "prop", "token", "expected", "actual", "severity", "message"):
                assert key in finding
            assert finding["file"] == (FIXTURES / case["file"]).relative_to(REPO_ROOT).as_posix()
            assert 1 <= finding["line"] <= line_count
            assert finding["prop"]
            assert finding["expected"]
            assert finding["actual"]
            assert "var(" not in finding["actual"]
    assert checked > 0


# ---------------------------------------------------------------------------
# Value handling: aliases, token-equal literals, unknown values
# ---------------------------------------------------------------------------
def test_token_alias_references_and_token_equal_literals_are_clean():
    text = """
.card {
  color: var(--color-text-primary);
  background-color: var(--color-bg-subtle);
  padding: var(--space-3) var(--space-4);
  gap: 0.5rem;
  font-size: 13px;
  line-height: 1.45;
  transition: opacity 120ms ease-out;
}
.accent {
  color: #0969DA;
  border-color: rgb(208, 215, 222);
}
"""
    result = design_system.lint_text(text, file="alias.css")
    assert result["findings"] == [], design_system.dump_result(result)


def test_local_var_aliases_are_resolved_and_unknown_vars_skipped():
    text = """
:root {
  --brand: #ff0000;
  --gap: 10px;
}
.button {
  color: var(--brand);
  padding: var(--gap);
  border-color: var(--unknown-border);
}
"""
    result = design_system.lint_text(text, file="local.css")
    assert _finding_pairs(result) == [("UX-SPACE-001", 8), ("color_token", 7)]
    assert len(result["findings"]) == 2


def test_unknown_values_are_skipped_conservatively():
    text = """
.unknown {
  color: hsl(210 50% 40%);
  background-color: rgba(255, 0, 0, 0.5);
  padding: calc(4px + 8px);
  margin: 5em;
  font-size: 1.2em;
  line-height: normal;
  border-color: var(--undefined-color);
  transition: opacity var(--motion-missing, 200ms);
}
"""
    result = design_system.lint_text(text, file="unknown.css")
    assert result["findings"] == [], design_system.dump_result(result)


def test_spacing_token_boundaries():
    result = design_system.lint_text(
        ".x { margin: 0 auto; padding: 0.5rem; gap: -4px; }",
        file="boundary.css",
    )
    assert result["findings"] == []
    result = design_system.lint_text(".x { padding: 6px; }", file="boundary.css")
    assert [finding["rule_id"] for finding in result["findings"]] == ["UX-SPACE-001"]
    assert result["findings"][0]["line"] == 1


def test_font_size_and_line_height_rule_boundaries():
    result = design_system.lint_text(
        ".small { font-size: 11px; line-height: 1.29; }\n"
        ".drift { font-size: 15px; line-height: 1.55; }\n"
        ".token { font-size: 12px; line-height: 1.2; }\n",
        file="type.css",
    )
    by_line = {(finding.get("rule_id") or finding.get("dimension"), finding["line"]) for finding in result["findings"]}
    assert by_line == {
        ("UX-TYPE-001", 1),
        ("UX-TYPE-002", 1),
        ("font_size_token", 2),
        ("line_height_token", 2),
    }


def test_motion_maps_to_catalog_rule_and_token_values_pass():
    result = design_system.lint_text(
        ".a { transition: opacity 120ms ease-out; }\n"
        ".b { animation: spin 0s linear; }\n"
        ".c { transition: all 333ms ease-in; }\n",
        file="motion.css",
    )
    assert [(finding["rule_id"], finding["line"]) for finding in result["findings"]] == [("UX-MOTION-001", 3)]
    finding = result["findings"][0]
    assert finding["actual"] == "all 333ms ease-in"
    assert finding["token"] == "motion"


# ---------------------------------------------------------------------------
# TSX/QSS, determinism, result contract
# ---------------------------------------------------------------------------
def test_tsx_findings_use_style_block_line():
    result = design_system.lint_file(FIXTURES / "negative" / "tsx-inline.tsx", root=REPO_ROOT)
    assert result["findings"]
    assert {finding["line"] for finding in result["findings"]} == {5}
    assert design_system.lint_file(
        FIXTURES / "positive" / "tsx-theme.tsx", root=REPO_ROOT
    )["findings"] == []


def test_qss_stack_inference_and_unsupported_sources():
    assert design_system.infer_stack("theme.qss") == "qt"
    assert design_system.infer_stack("theme.css") == "web"
    assert design_system.lint_file(FIXTURES / "positive" / "qt-theme.qss", root=REPO_ROOT)["findings"] == []
    with pytest.raises(ValueError):
        design_system.lint_text(".x { color: red; }", file="sheet.scss")
    with pytest.raises(ValueError):
        design_system.lint_text(".x { color: red; }", file="sheet.css", stack="winui")


def test_deterministic_output_is_byte_stable():
    case = next(case for case in CASES if case["file"] == "negative/web-deviations.css")
    first = design_system.dump_result(_lint_case(case))
    second = design_system.dump_result(_lint_case(case))
    assert first == second
    assert design_system.lint_text(".x { padding: 13px; }", file="z.css") == design_system.lint_text(
        ".x { padding: 13px; }", file="z.css"
    )


def test_lint_files_aggregates_and_sorts_findings():
    files = [
        FIXTURES / "negative" / "web-deviations.css",
        FIXTURES / "positive" / "web-tokens.css",
        FIXTURES / "negative" / "local-alias.css",
    ]
    result = design_system.lint_files(files, root=REPO_ROOT)
    assert result["files_checked"] == [
        "tests/fixtures/design_system/negative/web-deviations.css",
        "tests/fixtures/design_system/positive/web-tokens.css",
        "tests/fixtures/design_system/negative/local-alias.css",
    ]
    assert result["summary"]["warning"] == len(result["findings"])
    assert result["summary"]["fail"] == 0
    assert result["ok"] is False
    ordered = [
        (finding["file"], finding["line"], finding.get("rule_id") or finding.get("dimension"))
        for finding in result["findings"]
    ]
    assert ordered == sorted(ordered)


def test_result_contract_metadata():
    result = design_system.lint_text(".x { padding: 13px; }", file="meta.css")
    assert result["detector"] == "design_system_linter"
    assert result["linter_version"] == "1.0"
    assert result["token_set_version"] == TOKENS["token_set_version"]
    assert result["token_sha256"] == design_system.canonical_digest(TOKENS)
    assert result["catalog_version"] == CATALOG["catalog_version"]
    assert result["dimensions"] == list(design_system.DIMENSIONS)
    assert result["files_checked"] == ["meta.css"]
    assert result["ok"] is False
    assert result["summary"] == {"fail": 0, "warning": 1, "info": 0}


def test_invalid_custom_tokens_are_rejected():
    invalid = copy.deepcopy(TOKENS)
    del invalid["colors"]
    assert design_system.token_schema_errors(invalid)
    with pytest.raises(ValueError):
        design_system.lint_text(":root { color: #ffffff; }", file="x.css", tokens=invalid)

    invalid_color = copy.deepcopy(TOKENS)
    invalid_color["colors"]["color-broken"] = "not-a-color"
    assert design_system.token_schema_errors(invalid_color)
    with pytest.raises(ValueError):
        design_system.lint_text(":root { color: #ffffff; }", file="x.css", tokens=invalid_color)
