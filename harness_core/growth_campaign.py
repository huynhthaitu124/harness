from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_CATEGORIES = ["codex", "anthropic", "ollama", "mcp"]


def init_campaign(
    path: Path,
    *,
    target_hours: float,
    started_at: datetime | None = None,
    required_categories: list[str] | None = None,
) -> dict[str, Any]:
    campaign = {
        "version": 1,
        "started_at": (started_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "target_hours": float(target_hours),
        "required_categories": required_categories or DEFAULT_CATEGORIES,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(campaign, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return campaign


def campaign_status(
    path: Path,
    *,
    cycle_dir: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    campaign = json.loads(path.read_text(encoding="utf-8"))
    started_at = datetime.fromisoformat(campaign["started_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    elapsed_hours = max(0.0, (now - started_at).total_seconds() / 3600)
    target_hours = float(campaign["target_hours"])
    cycles = _load_cycles(cycle_dir)
    categories = sorted(_source_categories(cycles))
    missing = []
    if not cycles:
        missing.append("no_growth_cycles")
    for category in campaign.get("required_categories", DEFAULT_CATEGORIES):
        if category not in categories:
            missing.append(f"missing_category:{category}")
    if elapsed_hours < target_hours:
        verdict = "IN_PROGRESS"
    elif missing:
        verdict = "NEEDS_WORK"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "started_at": campaign["started_at"],
        "target_hours": target_hours,
        "elapsed_hours": round(elapsed_hours, 2),
        "remaining_hours": round(max(0.0, target_hours - elapsed_hours), 2),
        "cycle_count": len(cycles),
        "source_categories": categories,
        "missing": missing,
        "note": "Wall-clock campaign status is not a substitute for active goal-time verification.",
    }


def _load_cycles(cycle_dir: Path) -> list[dict[str, Any]]:
    cycles = []
    if not cycle_dir.exists():
        return cycles
    for path in sorted(cycle_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            cycles.append(payload)
    return cycles


def _source_categories(cycles: list[dict[str, Any]]) -> set[str]:
    categories: set[str] = set()
    for cycle in cycles:
        for source in cycle.get("sources", []):
            url = str(source.get("url", "")).lower()
            if "openai.com" in url or "codex" in url:
                categories.add("codex")
            if "anthropic.com" in url or "claude.com" in url or "claude-code" in url:
                categories.add("anthropic")
            if "ollama" in url:
                categories.add("ollama")
            if "modelcontextprotocol" in url or "mcp" in url:
                categories.add("mcp")
    return categories
