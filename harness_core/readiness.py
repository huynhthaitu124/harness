from __future__ import annotations

from typing import Any

from harness_core.local_model_gate import local_model_decision

CENTERS = ("codex", "claude", "antigravity")


def build_readiness_report(
    state: dict[str, Any],
    *,
    probes: dict[str, dict[str, Any]],
    local_probe: dict[str, Any] | None = None,
    machine: dict[str, Any] | None = None,
) -> dict[str, Any]:
    centers: dict[str, Any] = {}
    for center in CENTERS:
        probe = probes.get(center, {})
        quota = state.get("quotas", {}).get(center, {})
        reasons: list[str] = []
        if not probe.get("installed", False):
            status = "unavailable"
            reasons.append("CLI is not installed or not on PATH")
        elif not quota.get("available", True):
            status = "unavailable"
            reasons.append(str(quota.get("last_error", "quota marked unavailable")))
            if quota.get("reset_hint"):
                reasons.append(f"reset: {quota['reset_hint']}")
        elif int(quota.get("consecutive_failures", 0)) > 0:
            status = "degraded"
            reasons.append(f"{quota['consecutive_failures']} recent worker failure(s)")
        elif not probe.get("harness_connected", False):
            status = "degraded"
            reasons.append("shared harness is not connected/imported")
        else:
            status = "ready"
            reasons.append("CLI and shared harness are available")
        centers[center] = {"status": status, "reasons": reasons, "probe": probe, "quota": quota}

    report: dict[str, Any] = {
        "preferred_center": state.get("preferred_center", "auto"),
        "centers": centers,
        "ready_centers": [center for center, item in centers.items() if item["status"] == "ready"],
    }
    if local_probe is not None and machine is not None:
        gate = local_model_decision(machine, "light")
        if not local_probe.get("installed", False):
            local_status = "unavailable"
        elif not gate["allow"]:
            local_status = "blocked"
        elif local_probe.get("model_loaded", False):
            local_status = "ready"
        else:
            local_status = "idle"
        report["local_worker"] = {
            "status": local_status,
            "probe": local_probe,
            "machine": machine,
            "reasons": gate["reasons"],
        }
    return report
