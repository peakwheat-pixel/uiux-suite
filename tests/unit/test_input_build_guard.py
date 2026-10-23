from __future__ import annotations

import os

from uiux_engine import build_guard, input_policy, safety


def test_global_physical_input_denied_by_default():
    decision = input_policy.authorize("GLOBAL_PHYSICAL")
    assert decision["decision"] == "DENY"
    assert decision["reason"] == "GLOBAL_PHYSICAL_FORBIDDEN"


def test_global_physical_only_when_isolated_and_explicit():
    assert input_policy.authorize("GLOBAL_PHYSICAL", isolated=True)["decision"] == "DENY"
    assert input_policy.authorize("GLOBAL_PHYSICAL", explicit=True)["decision"] == "DENY"
    allowed = input_policy.authorize("GLOBAL_PHYSICAL", isolated=True, explicit=True)
    assert allowed["decision"] == "ALLOW"


def test_uia_read_allowed_but_action_requires_isolation():
    assert input_policy.authorize("UIA_READ", read_only=True)["decision"] == "ALLOW"
    assert input_policy.authorize("UIA_ACTION")["decision"] == "DENY"
    assert input_policy.authorize("UIA_ACTION", isolated=True)["decision"] == "ALLOW"


def test_unknown_channel_denied():
    assert input_policy.authorize("KEYBOARD")["decision"] == "DENY"


def test_build_guard_allows_known_test_command(tmp_path):
    result = build_guard.check("pytest tests -q", tmp_path)
    assert result["decision"] == "ALLOW"


def test_build_guard_denies_unknown_executable(tmp_path):
    result = build_guard.check("powershell -Command whoami", tmp_path)
    assert result["decision"] == "DENY"
    assert any("EXECUTABLE_NOT_ALLOWED" in reason for reason in result["reasons"])


def test_build_guard_denies_network_without_flag(tmp_path):
    result = build_guard.check("git push origin main", tmp_path)
    assert result["decision"] == "DENY"
    assert "NETWORK_REQUIRES_EXPLICIT_FLAG" in result["reasons"]


def test_build_guard_denies_outside_root(tmp_path):
    outside_path = "C:\\Windows\\setup.py" if os.name == "nt" else "/etc/setup.py"
    result = build_guard.check(f"python {outside_path}", tmp_path)
    assert result["decision"] == "DENY"
    assert any("PATH_OUTSIDE_ROOT" in reason for reason in result["reasons"])


def test_build_guard_allows_network_with_flag(tmp_path):
    assert build_guard.check("npm install", tmp_path, allow_network=True)["decision"] == "ALLOW"


def test_safety_metrics_zero_write():
    report = safety.metrics(
        [
            {"real_user_data_writes": 0, "protected_root_writes": 0, "blocked_actions": 2},
            {"real_user_data_writes": 0, "protected_root_writes": 0, "blocked_actions": 1},
        ]
    )
    assert report["zero_real_user_data_writes"] is True
    assert report["blocked_actions"] == 3
