from __future__ import annotations

import json
from typing import Any

from harness_core.token_ledger import record_usage


def parse_claude_usage(raw_json: str) -> dict[str, Any]:
    payload = _last_json_object(raw_json)
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    if not isinstance(usage, dict):
        raise ValueError("Claude output contains no usage object")
    input_tokens = sum(
        int(usage.get(key, 0))
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    output_tokens = int(usage.get("output_tokens", 0))
    if input_tokens + output_tokens <= 0:
        raise ValueError("Claude usage has zero tokens")
    return {
        "center": "claude",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": float(payload.get("total_cost_usd", 0.0)),
        "success": not bool(payload.get("is_error", False)),
        "attribution": _usage_attribution(payload),
        "raw_usage": usage,
    }


def parse_codex_usage(raw_jsonl: str) -> dict[str, Any]:
    events = _json_lines(raw_jsonl)
    usage: dict[str, Any] | None = None
    for event in events:
        found = _find_usage(event)
        if found is not None:
            usage = found
    if usage is None:
        raise ValueError("Codex JSONL contains no token usage event")
    input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)))
    output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)))
    if input_tokens + output_tokens <= 0:
        raise ValueError("Codex usage has zero tokens")
    return {
        "center": "codex",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": float(usage.get("cost_usd", 0.0)),
        "success": not any(event.get("type") in {"error", "turn.failed"} for event in events if isinstance(event, dict)),
        "attribution": {
            "cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
            "source": "codex-jsonl",
        },
        "raw_usage": usage,
    }


def ingest_usage(
    ledger_path,
    *,
    center: str,
    raw_output: str,
    label: str | None = None,
) -> dict[str, Any]:
    if center == "claude":
        parsed = parse_claude_usage(raw_output)
    elif center == "codex":
        parsed = parse_codex_usage(raw_output)
    else:
        raise ValueError("usage ingestion currently supports claude or codex")
    entry = record_usage(
        ledger_path,
        center=parsed["center"],
        input_tokens=parsed["input_tokens"],
        output_tokens=parsed["output_tokens"],
        cost_usd=parsed["cost_usd"],
        label=label or parsed["attribution"].get("source", ""),
    )
    return {"entry": entry, "parsed": parsed}


def _last_json_object(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("{"):
        payload = json.loads(stripped)
        if isinstance(payload, dict) and isinstance(payload.get("stdout"), str):
            return _last_json_object(payload["stdout"])
        if isinstance(payload, dict):
            return payload
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            return payload
    raise ValueError("output contains no JSON object")


def _json_lines(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _find_usage(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        for key in ("usage", "token_usage"):
            candidate = value.get(key)
            if isinstance(candidate, dict) and any(
                token_key in candidate
                for token_key in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens")
            ):
                return candidate
        for child in value.values():
            found = _find_usage(child)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_usage(child)
            if found is not None:
                return found
    return None


def _usage_attribution(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage", {})
    attribution = payload.get("usage_attribution") or payload.get("attribution") or {}
    if not isinstance(attribution, dict):
        attribution = {}
    attribution = dict(attribution)
    attribution.setdefault("source", "claude-json")
    for key in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        if key in usage:
            attribution[key] = int(usage.get(key, 0))
    return attribution
