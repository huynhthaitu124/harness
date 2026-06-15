from __future__ import annotations

from typing import Any


def local_model_decision(machine: dict[str, Any], task_complexity: str) -> dict[str, Any]:
    swap_total = max(1, int(machine.get("swap_total_mb", 1)))
    swap_used = int(machine.get("swap_used_mb", 0))
    free_percent = int(machine.get("memory_free_percent", 0))
    swap_ratio = swap_used / swap_total

    reasons: list[str] = []
    if swap_ratio > 0.7:
        reasons.append(f"swap usage is high ({swap_used}/{swap_total} MB)")
    if free_percent < 30:
        reasons.append(f"memory free percentage is low ({free_percent}%)")

    complexity = task_complexity.lower()
    if complexity in {"complex", "heavy", "rag-large"} and reasons:
        return {"allow": False, "max_context_tokens": 0, "reasons": reasons}
    if complexity in {"complex", "heavy", "rag-large"}:
        return {"allow": True, "max_context_tokens": 16384, "reasons": ["machine state allows bounded complex local work"]}
    if reasons and swap_ratio > 0.9:
        return {"allow": False, "max_context_tokens": 0, "reasons": reasons}
    return {"allow": True, "max_context_tokens": 8192, "reasons": reasons or ["machine state allows light local work"]}
