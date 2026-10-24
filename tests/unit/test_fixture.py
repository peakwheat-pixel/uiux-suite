"""TASK-01: declarative fixtures and environment preflight.

Under test:
- built-in fixtures load and cover the seven failure classes;
- apply_fixture materialises synthetic data only inside the sandbox;
- every failure class is detected with its expected code;
- A/B attribution keeps environment errors out of product-defect classification;
- the CLI exposes validate/preflight/apply.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from uiux_engine import fixture
from uiux_engine.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[2]
NEW_MANGA = ROOT / "fixtures" / "new-manga" / "minimal.json"
GENERIC = ROOT / "fixtures" / "generic" / "web-minimal.json"


def _facts(**overrides):
    facts = {
        "os": "windows",
        "python": "3.12",
        "env": {"M2RC1_PACKAGED": "1"},
        "executables": {},
        "ports": {9222: True, 8080: False},
        "free_gb": 10.0,
    }
    facts.update(overrides)
    return facts


def test_builtin_fixtures_load_and_cover_failure_classes():
    for path in (NEW_MANGA, GENERIC):
        payload = fixture.load_fixture(path)
        assert payload["fixture_id"].startswith("FIX-")
    new_manga = fixture.load_fixture(NEW_MANGA)
    assert set(new_manga["failure_class_coverage"]) == set(fixture.FAILURE_CLASSES)


def test_invalid_fixture_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "1.0", "fixture_id": "FIX-BAD"}), encoding="utf-8")
    with pytest.raises(fixture.FixtureError) as exc:
        fixture.load_fixture(bad)
    assert "FIXTURE_INVALID" in str(exc.value)


def test_unsupported_stack_is_reported():
    payload = fixture.load_fixture(GENERIC)
    payload = copy.deepcopy(payload)
    payload["project"]["stack"] = "unknown"
    problems = fixture.semantic_problems(payload)
    assert any("unsupported_stack" in problem for problem in problems)


def test_apply_materialises_only_inside_sandbox(tmp_path):
    payload = fixture.load_fixture(NEW_MANGA)
    sandbox = tmp_path / "sandbox"
    applied = fixture.apply_fixture(payload, sandbox)
    assert applied["fixture_id"] == "FIX-NEW-MANGA-MINIMAL"
    assert (sandbox / "newmanga-data" / "regions.json").is_file()
    assert (sandbox / "newmanga-data" / "pipeline_runs.json").is_file()
    assert (sandbox / "newmanga-data" / "catalog" / "catalog-snapshot.json").is_file()
    regions = json.loads((sandbox / "newmanga-data" / "regions.json").read_text(encoding="utf-8"))
    assert len(regions["regions"]) == 2
    catalog = json.loads((sandbox / "newmanga-data" / "catalog" / "catalog-snapshot.json").read_text(encoding="utf-8"))
    assert catalog["kind"] == "json_snapshot"
    assert catalog["tables"]["region"]
    for root in applied["roots"].values():
        assert sandbox.resolve() in Path(root).parents
    # real tree untouched
    assert not (ROOT / "newmanga-data").exists()


def test_readonly_escape_is_rejected(tmp_path):
    payload = copy.deepcopy(fixture.load_fixture(GENERIC))
    payload["roots"]["data_root"] = "../../outside"
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    with pytest.raises(fixture.FixtureError) as exc:
        fixture.apply_fixture(payload, sandbox)
    assert "READONLY_VIOLATION" in str(exc.value)

    payload = copy.deepcopy(fixture.load_fixture(GENERIC))
    payload["data"]["files"][0]["relative_path"] = "../escape.json"
    with pytest.raises(fixture.FixtureError) as exc:
        fixture.apply_fixture(payload, sandbox)
    assert "READONLY_VIOLATION" in str(exc.value)


def test_missing_executable_class(tmp_path):
    payload = fixture.load_fixture(NEW_MANGA)
    sandbox = tmp_path / "empty-sandbox"
    sandbox.mkdir()
    problems = fixture.preflight_problems(payload, _facts(), sandbox_root=sandbox)
    assert any(p["class"] == "missing_executable" and p["code"] == "EXECUTABLE_MISSING" for p in problems)


def test_missing_env_class():
    payload = fixture.load_fixture(NEW_MANGA)
    problems = fixture.preflight_problems(payload, _facts(env={}))
    assert any(p["class"] == "missing_env" and p["code"] == "ENV_VAR_MISSING" for p in problems)


def test_cdp_not_listening_is_classified():
    payload = fixture.load_fixture(NEW_MANGA)
    problems = fixture.preflight_problems(payload, _facts(ports={9222: False}))
    assert any(p["class"] == "port_occupied" and p["code"] == "CDP_PORT_NOT_LISTENING" for p in problems)


def test_http_port_busy_is_classified():
    payload = fixture.load_fixture(GENERIC)
    problems = fixture.preflight_problems(payload, _facts(ports={8080: True}))
    assert any(p["class"] == "port_occupied" and p["code"] == "PORT_OCCUPIED" for p in problems)


def test_unresolved_sandbox_placeholder_is_classified():
    payload = fixture.load_fixture(NEW_MANGA)
    problems = fixture.preflight_problems(payload, _facts())
    assert any(p["class"] == "data_root_missing" and p["code"] == "SANDBOX_ROOT_UNRESOLVED" for p in problems)


def test_clean_preflight_after_apply(tmp_path):
    payload = fixture.load_fixture(NEW_MANGA)
    sandbox = tmp_path / "sandbox"
    fixture.apply_fixture(payload, sandbox)
    problems = fixture.preflight_problems(payload, _facts(), sandbox_root=sandbox)
    assert problems == [], problems


def test_ab_attribution_keeps_environment_errors_out_of_product_defects():
    env_only = fixture.classify_ab_attribution(
        bad_problems=[{"class": "missing_executable", "code": "EXECUTABLE_MISSING", "detail": ""}],
        good_problems=[],
    )
    assert env_only["environment_authored"] is True
    assert env_only["product_defect_eligible"] is False

    product = fixture.classify_ab_attribution(
        bad_problems=[{"class": "missing_executable", "code": "EXECUTABLE_MISSING", "detail": ""}],
        good_problems=[],
        product_signal=True,
    )
    assert product["product_defect_eligible"] is True

    shared = fixture.classify_ab_attribution(
        bad_problems=[{"class": "missing_env", "code": "ENV_VAR_MISSING", "detail": ""}],
        good_problems=[{"class": "missing_env", "code": "ENV_VAR_MISSING", "detail": ""}],
    )
    assert shared["environment_authored"] is False
    assert shared["product_defect_eligible"] is True


def test_failure_class_matrix_matches_enum():
    matrix = fixture.failure_class_matrix()
    assert {item["class"] for item in matrix} == set(fixture.FAILURE_CLASSES)
    for item in matrix:
        assert item["detected_by"] and item["code"]


def test_cli_fixture_validate_and_apply(tmp_path, capsys):
    assert cli_main(["fixture", "validate", "--fixture", str(NEW_MANGA)]) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is True
    sandbox = tmp_path / "cli-sandbox"
    assert cli_main(["fixture", "apply", "--fixture", str(NEW_MANGA), "--sandbox", str(sandbox)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fixture_id"] == "FIX-NEW-MANGA-MINIMAL"
    assert (sandbox / "newmanga-data" / "regions.json").is_file()


def test_cli_fixture_preflight_failure_exit(tmp_path, capsys):
    sandbox = tmp_path / "cli-sandbox"
    code = cli_main(["fixture", "preflight", "--fixture", str(NEW_MANGA), "--sandbox", str(sandbox)])
    assert code == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["problems"]
