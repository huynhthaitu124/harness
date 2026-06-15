from __future__ import annotations

from typing import Any


def plan_next_growth_action(
    *,
    doctor: dict[str, Any],
    readiness: dict[str, Any],
    research: dict[str, Any],
    retrieval_eval: dict[str, Any],
    pending_feature: dict[str, Any] | None,
    experiment_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ready_centers = readiness.get("ready_centers", [])
    if not ready_centers:
        return _plan(
            "local_maintenance",
            "local",
            "No cloud center is currently ready; continue deterministic tests, indexes, audits, and docs.",
            ["run_local_checks", "record_evidence"],
            use_rag_first=False,
        )

    execution_center = _execution_center(ready_centers)
    research_center = _research_center(ready_centers)
    if not doctor.get("ok", False):
        return _plan(
            "repair_integrity",
            execution_center,
            "Harness doctor reports integrity or documentation drift.",
            ["inspect_doctor_issues", "write_failing_test", "repair", "run_doctor", "run_tests", "record_evidence"],
        )
    if retrieval_eval.get("verdict") != "PASS":
        return _plan(
            "repair_retrieval",
            execution_center,
            "Retrieval quality gate is not passing.",
            ["inspect_failed_cases", "write_failing_test", "improve_retrieval", "run_retrieval_eval", "run_tests", "record_evidence"],
            use_rag_first=True,
        )
    if int(research.get("changed_count", 0)) > 0:
        return _plan(
            "review_changed_sources",
            research_center,
            "Registered research sources changed and require evidence-backed review.",
            ["build_compact_source_diff", "review_changed_sources", "propose_one_change", "evaluate", "record_evidence"],
            use_rag_first=True,
        )
    if int(research.get("due_count", 0)) > 0:
        return _plan(
            "refresh_research",
            research_center,
            "Research sources are due by cadence.",
            ["refresh_due_sources", "review_changes", "record_evidence"],
            use_rag_first=True,
        )
    if experiment_plan and experiment_plan.get("verdict") == "READY":
        run = experiment_plan.get("run", {})
        plan = _plan(
            "run_token_experiment",
            run.get("center", execution_center),
            f"Token evidence is incomplete; run {run.get('variant', 'next')} experiment for {run.get('experiment_id', 'queued task')}.",
            [
                "build_requested_context",
                "run_center_command",
                "evaluate_experiment_output",
                "record_experiment_run",
                "refresh_health_report",
            ],
            use_rag_first=run.get("context_mode") != "raw_repo",
        )
        plan["experiment_run"] = run
        return plan
    if pending_feature:
        return _plan(
            "implement_pending_feature",
            execution_center,
            f"Pending default-fail feature: {pending_feature.get('description', pending_feature.get('id'))}",
            ["build_compact_context", "write_failing_test", "implement", "run_tests", "complete_feature_with_evidence"],
            use_rag_first=True,
        )
    return _plan(
        "explore_next_capability",
        research_center,
        "All current gates pass; research one bounded capability improvement.",
        ["route_research", "build_compact_context", "research_current_sources", "propose_one_change", "write_failing_test", "implement", "evaluate", "record_evidence"],
        use_rag_first=True,
    )


def _plan(action: str, center: str, reason: str, workflow: list[str], *, use_rag_first: bool = False) -> dict[str, Any]:
    return {
        "action": action,
        "center": center,
        "reason": reason,
        "use_rag_first": use_rag_first,
        "workflow": workflow,
        "required_evidence": ["tests or deterministic checks", "artifact paths", "evaluated growth cycle"],
        "destructive_actions_allowed": False,
        "command_policy_required": True,
    }


def _execution_center(ready_centers: list[str]) -> str:
    for center in ("codex", "claude", "antigravity"):
        if center in ready_centers:
            return center
    return ready_centers[0]


def _research_center(ready_centers: list[str]) -> str:
    for center in ("antigravity", "codex", "claude"):
        if center in ready_centers:
            return center
    return ready_centers[0]
