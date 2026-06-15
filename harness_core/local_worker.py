from __future__ import annotations

import shlex
from typing import Any

from harness_core.local_model_gate import local_model_decision


def plan_local_worker(
    task: str,
    *,
    machine: dict[str, Any],
    task_complexity: str,
    model: str = "qwen35-codex-local",
) -> dict[str, Any]:
    gate = local_model_decision(machine, task_complexity)
    if not gate["allow"]:
        return {
            "mode": "extractive",
            "use_ollama": False,
            "max_context_tokens": 0,
            "reasons": gate["reasons"],
            "fallback": "Use indexed search and deterministic context packing until memory/swap improves.",
        }

    prompt = f"Summarize or transform this task locally with concise output: {task}"
    command = f"ollama run {shlex.quote(model)} {shlex.quote(prompt)}"
    return {
        "mode": "ollama",
        "use_ollama": True,
        "model": model,
        "command": command,
        "max_context_tokens": gate["max_context_tokens"],
        "reasons": gate["reasons"],
    }
