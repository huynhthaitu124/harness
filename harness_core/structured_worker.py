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


def validate_structured_worker_output(raw_output: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate a local worker response against a small JSON-schema subset."""
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return {"valid": False, "errors": [f"invalid_json:{exc.msg}"], "payload": None}
    errors = _validate_value(payload, schema, "$")
    return {"valid": not errors, "errors": errors, "payload": payload}


def _validate_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected and not _matches_type(value, expected):
        return [f"{path}:expected_{expected}"]
    if expected == "object":
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}.{key}:missing_required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(_validate_value(value[key], child_schema, f"{path}.{key}"))
    elif expected == "array":
        item_schema = schema.get("items")
        if isinstance(item_schema, dict) and isinstance(value, list):
            for index, item in enumerate(value):
                errors.extend(_validate_value(item, item_schema, f"{path}[{index}]"))
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}:not_in_enum")
    return errors


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True
