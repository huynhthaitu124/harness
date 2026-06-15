from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

LIMIT_MARKERS = ("session limit", "usage limit", "quota exceeded", "rate limit", "api_error_status\":429")
RESET_RE = re.compile(r"(?:resets?|try again at)\s+([^\n\r\"]+)", re.IGNORECASE)


def apply_worker_feedback(
    state: dict[str, Any],
    *,
    center: str,
    returncode: int,
    output: str,
) -> dict[str, Any]:
    updated = deepcopy(state)
    quota = updated.setdefault("quotas", {}).setdefault(center, {})
    if returncode == 0:
        quota["available"] = True
        quota.pop("remaining_percent", None)
        quota.pop("reset_hint", None)
        quota.pop("last_error", None)
        quota.pop("consecutive_failures", None)
        return updated

    lowered = output.lower()
    if any(marker in lowered for marker in LIMIT_MARKERS):
        quota["available"] = False
        quota["remaining_percent"] = 0
        match = RESET_RE.search(output)
        if match:
            quota["reset_hint"] = match.group(1).strip(" .")
        quota["last_error"] = "worker quota/session limit"
    else:
        quota["consecutive_failures"] = int(quota.get("consecutive_failures", 0)) + 1
        quota["last_error"] = output.strip()[:500] or f"worker exited with code {returncode}"
    return updated
