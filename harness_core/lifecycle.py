"""Lifecycle hook system — inline safety regulator inside the execution loop.

Hooks observe every tool call (before/after/error) and can:
  - cancel the call (before_tool returning action="cancel")
  - fire a webhook
  - record to trajectory
  - require confirmation

Config lives in .harness/hooks.json per project.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_EVENTS  = ("before_tool", "after_tool", "on_error", "on_decision", "on_session_start", "on_session_end")
VALID_ACTIONS = ("allow", "cancel", "webhook", "record", "require_confirm", "record_trajectory_failure")


def default_hooks() -> list[dict[str, Any]]:
    return [
        {
            "event":        "on_error",
            "tool_pattern": "*",
            "action":       "record_trajectory_failure",
            "enabled":      True,
        },
        {
            "event":        "after_tool",
            "tool_pattern": "*",
            "action":       "record",
            "enabled":      True,
        },
    ]


def load_hooks(root: Path) -> list[dict[str, Any]]:
    hooks_path = root / ".harness" / "hooks.json"
    if not hooks_path.exists():
        return default_hooks()
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
        return data.get("hooks", default_hooks())
    except Exception:
        return default_hooks()


def save_hooks(root: Path, hooks: list[dict[str, Any]]) -> None:
    hooks_path = root / ".harness" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(
        json.dumps({"version": 1, "hooks": hooks}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def register_hook(
    root: Path,
    *,
    event: str,
    tool_pattern: str = "*",
    action: str,
    webhook_url: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    if event not in VALID_EVENTS:
        raise ValueError(f"unknown event: {event}. Valid: {VALID_EVENTS}")
    if action not in VALID_ACTIONS:
        raise ValueError(f"unknown action: {action}. Valid: {VALID_ACTIONS}")
    hooks = load_hooks(root)
    hook = {
        "event":        event,
        "tool_pattern": tool_pattern,
        "action":       action,
        "enabled":      enabled,
    }
    if webhook_url:
        hook["webhook_url"] = webhook_url
    hooks.append(hook)
    save_hooks(root, hooks)
    return hook


def fire_event(
    root: Path,
    event: str,
    *,
    tool: str,
    session_id: str | None = None,
    center: str = "",
    project: str = "",
    result_status: str = "",
    duration_ms: int = 0,
    tokens: int = 0,
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fire all hooks matching this event+tool. Returns aggregate result."""
    hooks = load_hooks(root)
    matched = [
        h for h in hooks
        if h.get("enabled", True)
        and h.get("event") == event
        and _matches_pattern(tool, h.get("tool_pattern", "*"))
    ]

    ctx: dict[str, Any] = {
        "event":         event,
        "tool":          tool,
        "session_id":    session_id,
        "center":        center,
        "project":       project,
        "result_status": result_status,
        "duration_ms":   duration_ms,
        "tokens":        tokens,
        "error":         error,
        "ts":            datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }

    results: list[dict[str, Any]] = []
    cancelled = False
    for hook in matched:
        action = hook.get("action", "allow")
        outcome: dict[str, Any] = {"hook_action": action, "event": event, "tool": tool}

        if action == "cancel":
            cancelled = True
            outcome["cancelled"] = True

        elif action == "webhook":
            url = hook.get("webhook_url")
            if url:
                outcome["webhook_sent"] = _send_webhook(url, ctx)
            else:
                outcome["webhook_sent"] = False
                outcome["error"] = "no webhook_url configured"

        elif action == "record_trajectory_failure" and session_id:
            # signal to caller to close trajectory with failure
            outcome["signal"] = "trajectory_failure"

        elif action == "record":
            # lightweight — just log to .harness/events.jsonl
            _append_event(root, ctx)
            outcome["recorded"] = True

        results.append(outcome)

    return {
        "event":     event,
        "tool":      tool,
        "cancelled": cancelled,
        "hooks_fired": len(matched),
        "results":   results,
    }


def list_hooks(root: Path) -> list[dict[str, Any]]:
    return load_hooks(root)


# ── internal ─────────────────────────────────────────────────────────────────

def _matches_pattern(tool: str, pattern: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return tool.startswith(pattern[:-1])
    if pattern.startswith("*"):
        return tool.endswith(pattern[1:])
    return tool == pattern


def _send_webhook(url: str, payload: dict[str, Any]) -> bool:
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "harness-webhook/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except Exception:
        return False


def _append_event(root: Path, ctx: dict[str, Any]) -> None:
    events_path = root / ".harness" / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ctx, ensure_ascii=False) + "\n")
