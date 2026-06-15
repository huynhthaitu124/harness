from __future__ import annotations

import json
import shlex
from typing import Any

from harness_core.local_model_gate import local_model_decision


def plan_structured_local_worker(
    task: str,
    *,
    machine: dict[str, Any],
    task_complexity: str,
    schema: dict[str, Any],
    model: str = "qwen35-codex-local",
) -> dict[str, Any]:
    gate = local_model_decision(machine, task_complexity)
    if not gate["allow"]:
        return {
            "mode": "extractive",
            "use_ollama": False,
            "max_context_tokens": 0,
            "reasons": gate["reasons"],
            "fallback": "Use deterministic contextual chunks or indexed packs before retrying local structured generation.",
        }

    prompt = (
        "Respond only with JSON that validates against the supplied schema. "
        f"Task: {task}"
    )
    format_spec = {"type": "json_schema", "json_schema": {"name": "harness_local_worker_result", "schema": schema}}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "format": schema,
        "stream": False,
    }
    payload_text = json.dumps(payload, ensure_ascii=False)
    command = "ollama_host=${OLLAMA_HOST:-http://localhost:11434}; curl -s \"$ollama_host/api/chat\" -d " + shlex.quote(
        payload_text
    )
    return {
        "mode": "structured_ollama",
        "use_ollama": True,
        "model": model,
        "prompt": prompt,
        "format": format_spec,
        "ollama_payload": payload,
        "command": command,
        "max_context_tokens": gate["max_context_tokens"],
        "reasons": gate["reasons"],
    }
