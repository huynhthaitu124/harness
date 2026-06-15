from __future__ import annotations

import math
from typing import Any, Callable

from harness_core.local_model_gate import local_model_decision

StructuredRunner = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]


def plan_local_rag_pipeline(
    task: str,
    *,
    chunk_count: int,
    machine: dict[str, Any],
    installed_models: list[str],
    model: str = "qwen35-codex-local",
    map_batch_size: int = 4,
) -> dict[str, Any]:
    gate = local_model_decision(machine, "complex")
    if not gate["allow"]:
        return {
            "mode": "retrieval_only",
            "use_ollama": False,
            "task": task,
            "stages": ["hybrid_retrieve", "build_context_pack"],
            "reasons": gate["reasons"],
            "fallback": "Send only the compact context pack to a ready cloud center or continue deterministic analysis.",
        }
    installed = any(name == model or name.startswith(f"{model}:") for name in installed_models)
    if not installed:
        return {
            "mode": "model_setup_required",
            "use_ollama": False,
            "task": task,
            "model": model,
            "stages": ["hybrid_retrieve", "build_context_pack"],
            "needs_model": True,
            "pull_command": f"ollama pull {model}",
            "reasons": gate["reasons"],
        }
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "evidence"],
    }
    return {
        "mode": "structured_map_reduce",
        "use_ollama": True,
        "task": task,
        "model": model,
        "stages": ["hybrid_retrieve", "semantic_rerank_if_available", "map", "reduce", "verify"],
        "map_batch_size": map_batch_size,
        "map_batch_count": math.ceil(max(0, chunk_count) / map_batch_size),
        "max_parallel": 1,
        "max_context_tokens": gate["max_context_tokens"],
        "output_schema": output_schema,
        "reasons": gate["reasons"],
    }


def execute_local_rag_pipeline(
    plan: dict[str, Any],
    chunks: list[str],
    *,
    runner: StructuredRunner,
) -> dict[str, Any]:
    if not plan.get("use_ollama") or plan.get("mode") != "structured_map_reduce":
        return {"mode": plan.get("mode"), "executed": False, "verification": {"verdict": "SKIPPED"}}
    batch_size = int(plan.get("map_batch_size", 4))
    schema = plan["output_schema"]
    task = str(plan.get("task", ""))
    mapped = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        mapped.append(runner("map", {"task": task, "chunks": batch}, schema))
    result = runner("reduce", {"task": task, "mapped": mapped}, schema)
    missing = [field for field in schema.get("required", []) if field not in result]
    return {
        "mode": plan["mode"],
        "executed": True,
        "map_result_count": len(mapped),
        "result": result,
        "verification": {"verdict": "PASS" if not missing else "NEEDS_WORK", "missing": missing},
    }
