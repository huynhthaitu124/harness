from __future__ import annotations

from typing import Any

TOKEN_MEASURED_CENTERS = {"codex", "claude"}


def aggregate_health(
    *,
    tests: dict[str, Any],
    doctor: dict[str, Any],
    mcp: dict[str, Any],
    retrieval: dict[str, Any],
    research: dict[str, Any],
    readiness: dict[str, Any],
    campaign: dict[str, Any],
    experiments: dict[str, Any] | None = None,
    security: dict[str, Any] | None = None,
    context_packs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    if not tests.get("passed", False):
        failures.append("tests_failed")
    if not doctor.get("ok", False):
        failures.append("doctor_failed")
    if mcp.get("verdict") != "PASS":
        failures.append("mcp_conformance_failed")
    if retrieval.get("verdict") != "PASS":
        failures.append("retrieval_eval_failed")
    if security is not None and security.get("verdict") != "PASS":
        failures.append("mcp_security_failed")
    if context_packs is not None and context_packs.get("verdict") != "PASS":
        failures.append("context_pack_audit_failed")
    due_count = int(research.get("due_count", 0))
    changed_count = int(research.get("changed_count", 0))
    if due_count:
        warnings.append(f"due_research_sources:{due_count}")
    if changed_count:
        warnings.append(f"changed_research_sources:{changed_count}")
    if not readiness.get("ready_centers", []):
        warnings.append("no_ready_cloud_center")
    if campaign.get("verdict") != "PASS":
        warnings.append(f"campaign:{campaign.get('verdict', 'unknown')}")
    if experiments is None:
        warnings.append("token_evidence_unavailable")
        experiments = {"verdict": "UNKNOWN", "missing_centers": [], "non_saving_centers": []}
    elif experiments.get("verdict") == "INCOMPLETE":
        missing_centers = [center for center in experiments.get("missing_centers", []) if center in TOKEN_MEASURED_CENTERS]
        missing = ",".join(sorted(missing_centers))
        warnings.append(f"token_evidence_missing:{missing}")
    elif experiments.get("verdict") == "REGRESSION":
        non_saving_centers = [center for center in experiments.get("non_saving_centers", []) if center in TOKEN_MEASURED_CENTERS]
        centers = ",".join(sorted(non_saving_centers))
        warnings.append(f"token_regression:{centers}")
    if failures:
        verdict = "NEEDS_WORK"
    elif warnings:
        verdict = "PASS_WITH_CONSTRAINTS"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "failures": failures,
        "warnings": warnings,
        "summary": {
            "tests": tests,
            "doctor": {"ok": doctor.get("ok"), "issue_count": len(doctor.get("issues", []))},
            "mcp": {"verdict": mcp.get("verdict"), "tool_count": mcp.get("tool_count")},
            "retrieval": {"verdict": retrieval.get("verdict"), "recall_at_k": retrieval.get("recall_at_k"), "mrr": retrieval.get("mrr")},
            "research": {"due_count": due_count, "changed_count": changed_count},
            "readiness": {"ready_centers": readiness.get("ready_centers", [])},
            "campaign": {"verdict": campaign.get("verdict"), "elapsed_hours": campaign.get("elapsed_hours")},
            "experiments": {
                "verdict": experiments.get("verdict"),
                "valid_pair_count": experiments.get("valid_pair_count", 0),
                "missing_centers": experiments.get("missing_centers", []),
                "non_saving_centers": experiments.get("non_saving_centers", []),
            },
            "security": {"verdict": None if security is None else security.get("verdict"), "warnings": [] if security is None else security.get("warnings", [])},
            "context_packs": {
                "verdict": None if context_packs is None else context_packs.get("verdict"),
                "pack_count": 0 if context_packs is None else context_packs.get("pack_count", 0),
                "failures": [] if context_packs is None else context_packs.get("failures", []),
            },
        },
    }
