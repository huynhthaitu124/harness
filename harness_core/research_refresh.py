from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_core.research_registry import (
    due_research_sources,
    init_research_registry,
    refresh_research_sources,
    research_registry_report,
)


DEFAULT_RESEARCH_SOURCES = [
    {
        "title": "OpenAI Codex changelog",
        "url": "https://developers.openai.com/codex/changelog",
        "category": "codex",
        "channel": "official",
        "refresh_days": 3,
    },
    {
        "title": "OpenAI Codex best practices",
        "url": "https://developers.openai.com/codex/learn/best-practices",
        "category": "codex",
        "channel": "official",
        "refresh_days": 14,
    },
    {
        "title": "Anthropic Claude Code changelog",
        "url": "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
        "category": "claude",
        "channel": "official",
        "refresh_days": 3,
    },
    {
        "title": "Anthropic memory tool",
        "url": "https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool",
        "category": "claude",
        "channel": "official",
        "refresh_days": 14,
    },
    {
        "title": "Ollama structured outputs",
        "url": "https://docs.ollama.com/capabilities/structured-outputs",
        "category": "ollama",
        "channel": "official",
        "refresh_days": 14,
    },
    {
        "title": "Ollama embeddings",
        "url": "https://docs.ollama.com/capabilities/embeddings",
        "category": "ollama",
        "channel": "official",
        "refresh_days": 14,
    },
    {
        "title": "MCP latest specification",
        "url": "https://modelcontextprotocol.io/specification/2025-11-25",
        "category": "mcp",
        "channel": "official",
        "refresh_days": 21,
    },
    {
        "title": "MCP roadmap",
        "url": "https://modelcontextprotocol.io/development/roadmap",
        "category": "mcp",
        "channel": "official",
        "refresh_days": 14,
    },
    {
        "title": "Antigravity Agent docs",
        "url": "https://ai.google.dev/gemini-api/docs/antigravity-agent",
        "category": "antigravity",
        "channel": "official",
        "refresh_days": 7,
    },
]


def default_research_registry_path(root: Path) -> Path:
    return root / ".harness" / "research" / "sources.json"


def ensure_default_research_registry(root: Path, *, path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_research_registry_path(root)
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return init_research_registry(registry_path, DEFAULT_RESEARCH_SOURCES)


def refresh_default_research(
    root: Path,
    *,
    force: bool = False,
    fetcher: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    registry_path = default_research_registry_path(root)
    ensure_default_research_registry(root, path=registry_path)
    due_before = due_research_sources(registry_path, now=now)
    refresh = refresh_research_sources(registry_path, fetcher=fetcher, now=now, force=force)
    report = research_registry_report(registry_path, now=now)
    payload = {
        "root": str(root),
        "registry_path": str(registry_path),
        "checked_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "force": force,
        "due_before_count": len(due_before),
        "refresh": refresh,
        "report": report,
        "next_action": _next_action(refresh, report),
    }
    out_path = root / ".harness" / "research" / "last-refresh.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _next_action(refresh: dict[str, Any], report: dict[str, Any]) -> str:
    if refresh.get("errors"):
        return "review_fetch_errors"
    if int(refresh.get("changed_count", 0)) > 0 or int(report.get("changed_count", 0)) > 0:
        return "write_findings_and_plan_one_harness_update"
    if int(report.get("due_count", 0)) > 0:
        return "retry_due_sources_later"
    return "no_update_needed"
