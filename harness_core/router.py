from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CENTERS = ("codex", "claude", "antigravity")
BUDGET_WEIGHTS = {"low": 1.0, "medium": 2.0, "high": 4.0}


def default_state() -> dict[str, Any]:
    return {
        "preferred_center": "auto",
        "quotas": {
            "codex": {"available": True, "relative_budget": "medium"},
            "claude": {"available": True, "relative_budget": "low"},
            "antigravity": {"available": True, "relative_budget": "high"},
        },
        "routing_policy": {
            "research_heavy_keywords": [
                "research",
                "scan",
                "codebase",
                "log",
                "logs",
                "summarize",
                "tổng hợp",
                "nghiên cứu",
                "đọc repo",
                "đọc code",
            ],
            "coding_keywords": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup"],
        },
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    state = default_state()
    state.update(loaded)
    state["quotas"].update(loaded.get("quotas", {}))
    state["routing_policy"].update(loaded.get("routing_policy", {}))
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def choose_center(
    task: str,
    state: dict[str, Any] | None = None,
    *,
    usage_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = state or default_state()
    task_lower = task.lower()
    reasons: list[str] = []

    preferred = state.get("preferred_center", "auto")
    quotas = state.get("quotas", {})

    center = None
    if preferred in CENTERS:
        if quotas.get(preferred, {}).get("available", True):
            center = preferred
            reasons.append(f"preferred center {preferred} is available")
        else:
            reasons.append(f"preferred center {preferred} is unavailable")

    routing_metrics: dict[str, Any] = {}
    if center is None:
        center, routing_metrics, adaptive_reasons = _best_available_center(task_lower, quotas, usage_summary)
        reasons.extend(adaptive_reasons)
        reasons.append(f"selected {center} by cost/capacity policy")

    research_terms = state.get("routing_policy", {}).get("research_heavy_keywords", [])
    coding_terms = state.get("routing_policy", {}).get("coding_keywords", [])
    use_rag_first = any(term.lower() in task_lower for term in research_terms)
    likely_coding = any(term.lower() in task_lower for term in coding_terms)

    workflow = []
    if use_rag_first:
        workflow.append("rag_summarize")
    if likely_coding and center != "codex":
        workflow.append(f"delegate_{center}")
    elif likely_coding:
        workflow.append("codex_preflight")
        workflow.append("codex_execute")
    if not workflow:
        workflow.append(f"{center}_answer")
    workflow.append("record_handoff")

    decision = {
        "center": center,
        "use_rag_first": use_rag_first,
        "workflow": workflow,
        "reasons": reasons,
    }
    if routing_metrics:
        decision["routing_metrics"] = routing_metrics
    return decision


def _best_available_center(
    task_lower: str,
    quotas: dict[str, Any],
    usage_summary: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], list[str]]:
    available = [center for center in CENTERS if quotas.get(center, {}).get("available", True)]
    if not available:
        return "codex", {}, ["no center reported available; using codex fallback"]

    reasons: list[str] = []
    eligible = []
    for center in available:
        remaining = quotas.get(center, {}).get("remaining_percent")
        if remaining is not None and float(remaining) <= 5:
            reasons.append(f"{center} has low remaining quota ({remaining}%)")
            continue
        eligible.append(center)
    if not eligible:
        eligible = available
        reasons.append("all centers have low remaining quota; ranking all available centers")

    by_center = (usage_summary or {}).get("by_center", {})
    metrics: dict[str, Any] = {}
    for center in eligible:
        quota = quotas.get(center, {})
        budget_weight = BUDGET_WEIGHTS.get(str(quota.get("relative_budget", "medium")), 2.0)
        observed = by_center.get(center, {})
        observed_tokens = int(observed.get("input_tokens", 0)) + int(observed.get("output_tokens", 0))
        normalized_tokens = observed_tokens / budget_weight
        affinity = _task_affinity(task_lower, center)
        remaining = quota.get("remaining_percent")
        quota_penalty = 0.0 if remaining is None else max(0.0, (50.0 - float(remaining)) * 1000.0)
        consecutive_failures = int(quota.get("consecutive_failures", 0))
        failure_penalty = consecutive_failures * 25000.0
        score = normalized_tokens + quota_penalty + failure_penalty + affinity
        metrics[center] = {
            "observed_tokens": observed_tokens,
            "budget_weight": budget_weight,
            "normalized_tokens": round(normalized_tokens, 2),
            "remaining_percent": remaining,
            "consecutive_failures": consecutive_failures,
            "failure_penalty": failure_penalty,
            "score": round(score, 2),
        }
        if consecutive_failures:
            reasons.append(f"{center} has {consecutive_failures} recent worker failure(s)")

    center = min(eligible, key=lambda item: (metrics[item]["score"], CENTERS.index(item)))
    if usage_summary:
        reasons.append("ranked available centers by normalized observed usage and quota signals")
    return center, metrics, reasons


def _task_affinity(task_lower: str, center: str) -> float:
    if any(term in task_lower for term in ("huge", "nhiều token", "long")):
        return -25000.0 if center == "antigravity" else 0.0
    if any(term in task_lower for term in ("code", "fix", "refactor", "implement", "test")):
        if center == "claude":
            return -15000.0
        if center == "codex":
            return -10000.0
    if any(term in task_lower for term in ("cheap", "ít token", "budget")) and center == "claude":
        return -10000.0
    return 0.0
