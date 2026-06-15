from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FeatureStateError(ValueError):
    pass


def init_feature_list(path: Path, titles: list[str]) -> dict[str, Any]:
    data = {
        "version": 1,
        "created_at": _now(),
        "features": [
            {
                "id": index + 1,
                "title": title,
                "status": "pending",
                "passes": False,
                "evidence": [],
            }
            for index, title in enumerate(titles)
        ],
    }
    _write(path, data)
    return data


def next_feature(path: Path) -> dict[str, Any] | None:
    data = _read(path)
    for feature in data.get("features", []):
        if feature.get("status") != "done" or not feature.get("passes"):
            return feature
    return None


def complete_feature(path: Path, feature_id: int, evidence: list[str]) -> dict[str, Any]:
    if not evidence:
        raise FeatureStateError("Cannot complete a feature without evidence")
    data = _read(path)
    for feature in data.get("features", []):
        if feature.get("id") == feature_id:
            feature["status"] = "done"
            feature["passes"] = True
            feature["evidence"] = evidence
            feature["completed_at"] = _now()
            _write(path, data)
            return feature
    raise FeatureStateError(f"Feature id not found: {feature_id}")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
