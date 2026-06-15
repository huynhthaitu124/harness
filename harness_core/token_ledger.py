from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def record_usage(
    path: Path,
    *,
    center: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    label: str | None = None,
) -> dict[str, Any]:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "center": center,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "label": label or "",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def summarize_usage(path: Path) -> dict[str, Any]:
    total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    by_center: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return {"total": total, "by_center": by_center}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        center = entry["center"]
        bucket = by_center.setdefault(center, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        for key in total:
            bucket[key] += entry[key]
            total[key] += entry[key]
    total["cost_usd"] = round(total["cost_usd"], 6)
    for bucket in by_center.values():
        bucket["cost_usd"] = round(bucket["cost_usd"], 6)
    return {"total": total, "by_center": by_center}
