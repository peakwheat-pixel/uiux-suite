"""OS input authorization policy (M6).

Global physical keyboard/mouse injection is denied by default. Test channels
must be explicitly scoped, and native UIA is read-only unless the caller
declares a physical action under an isolated test run.
"""
from __future__ import annotations

from typing import Any

CHANNELS = ("QTEST", "WEBDRIVER", "UIA_READ", "UIA_ACTION", "GLOBAL_PHYSICAL", "OS_DIALOG")
DECISIONS = ("ALLOW", "DENY")


def authorize(channel: str, *, isolated: bool = False, read_only: bool = False, explicit: bool = False) -> dict[str, Any]:
    channel = str(channel).upper()
    if channel not in CHANNELS:
        return {"decision": "DENY", "channel": channel, "reason": "UNKNOWN_CHANNEL"}
    if channel == "GLOBAL_PHYSICAL":
        allowed = isolated and explicit
        return {
            "decision": "ALLOW" if allowed else "DENY",
            "channel": channel,
            "reason": "ISOLATED_EXPLICIT" if allowed else "GLOBAL_PHYSICAL_FORBIDDEN",
        }
    if channel == "UIA_ACTION" and not isolated:
        return {"decision": "DENY", "channel": channel, "reason": "UIA_ACTION_REQUIRES_ISOLATION"}
    if channel == "OS_DIALOG" and not isolated:
        return {"decision": "DENY", "channel": channel, "reason": "OS_DIALOG_REQUIRES_ISOLATION"}
    if channel in ("UIA_READ", "QTEST", "WEBDRIVER"):
        return {"decision": "ALLOW", "channel": channel, "reason": "READ_ONLY_OR_TEST_CHANNEL" if read_only else "TEST_CHANNEL"}
    return {"decision": "ALLOW", "channel": channel, "reason": "ISOLATED"}


def summary() -> dict[str, Any]:
    return {
        "default": "DENY",
        "global_physical": "DENY unless isolated+explicit",
        "uia_read": "ALLOW (read-only)",
        "uia_action": "DENY outside isolated run",
        "channels": list(CHANNELS),
    }
