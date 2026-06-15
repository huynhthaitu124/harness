from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_growth_cycle(
    root: Path,
    *,
    topic: str,
    sources: list[dict[str, str]],
    actions: list[str],
) -> dict[str, Any]:
    cycles_dir = root / "production_artifacts" / "self_growth"
    cycles_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cycle_path = cycles_dir / f"{timestamp}-{_slug(topic)}.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "sources": sources,
        "actions": actions,
        "action_count": len(actions),
    }
    cycle_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"cycle_path": str(cycle_path), "action_count": len(actions)}


def _slug(text: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in text).split("-") if part)[:80]
