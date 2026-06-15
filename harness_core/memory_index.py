from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERM_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def record_memory(
    path: Path,
    *,
    content: str,
    source: str,
    kind: str,
    tags: list[str] | None = None,
    importance: float = 0.5,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
    for entry in _read_memories(path):
        if entry["content_hash"] == content_hash:
            return {"created": False, "memory": entry}
    entry = {
        "timestamp": (timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "content_hash": content_hash,
        "source": source,
        "kind": kind,
        "tags": tags or [],
        "importance": max(0.0, min(1.0, float(importance))),
        "content": content.strip(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"created": True, "memory": entry}


def search_memories(
    path: Path,
    query: str,
    *,
    top_k: int = 5,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    query_terms = set(_terms(query))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    results = []
    for entry in _read_memories(path):
        memory_terms = set(_terms(f"{entry['content']} {' '.join(entry.get('tags', []))} {entry['source']}"))
        overlap = len(query_terms & memory_terms)
        if query_terms and overlap == 0:
            continue
        relevance = overlap / max(1, len(query_terms))
        timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
        age_days = max(0.0, (now - timestamp).total_seconds() / 86400)
        recency = math.exp(-age_days / 90.0)
        importance = float(entry.get("importance", 0.5))
        score = relevance * 0.65 + importance * 0.25 + recency * 0.10
        results.append(
            {
                **entry,
                "score": round(score, 6),
                "relevance": round(relevance, 4),
                "recency": round(recency, 4),
                "age_days": round(age_days, 2),
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["source"]))[:top_k]


def build_memory_pack(path: Path, query: str, *, top_k: int = 5, max_chars: int = 3000) -> str:
    sections = [f"# Memory pack\nquery: {query}\n"]
    for memory in search_memories(path, query, top_k=top_k):
        section = (
            f"\n## {memory['kind']}\n"
            f"source: {memory['source']}\n"
            f"timestamp: {memory['timestamp']}\n"
            f"score: {memory['score']}\n"
            f"{memory['content']}\n"
        )
        current = "".join(sections)
        remaining = max_chars - len(current)
        if remaining <= 0:
            break
        sections.append(section[:remaining])
    return "".join(sections)[:max_chars]


def sync_artifact_memories(root: Path, path: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    cycle_dir = root / "production_artifacts" / "self_growth"
    cycle_paths = sorted(cycle_dir.glob("*.json")) if cycle_dir.exists() else []
    for artifact in cycle_paths:
        payload = _read_json_object(artifact)
        if not payload or not payload.get("topic"):
            continue
        actions = "; ".join(str(action) for action in payload.get("actions", []))
        candidates.append(
            {
                "content": f"Growth cycle {payload['topic']}. Actions: {actions}".strip(),
                "source": artifact.relative_to(root).as_posix(),
                "kind": "growth_cycle",
                "tags": ["self-growth", str(payload["topic"])],
                "importance": 0.75,
            }
        )
    handoff_dir = root / "production_artifacts" / "handoffs"
    handoff_paths = sorted(handoff_dir.glob("*.json")) if handoff_dir.exists() else []
    for artifact in handoff_paths:
        payload = _read_json_object(artifact)
        if not payload or not payload.get("summary"):
            continue
        candidates.append(
            {
                "content": (
                    f"Handoff {payload.get('title', artifact.stem)} from {payload.get('from_center', 'unknown')} "
                    f"to {payload.get('to_center', 'unknown')}. {payload['summary']} "
                    f"Fingerprint: {payload.get('task_fingerprint', 'unknown')}."
                ),
                "source": artifact.relative_to(root).as_posix(),
                "kind": "handoff",
                "tags": ["handoff", str(payload.get("from_center", "")), str(payload.get("to_center", ""))],
                "importance": 0.9,
            }
        )
    created_count = 0
    duplicate_count = 0
    for candidate in candidates:
        result = record_memory(path, **candidate)
        if result["created"]:
            created_count += 1
        else:
            duplicate_count += 1
    return {
        "path": str(path),
        "candidate_count": len(candidates),
        "created_count": created_count,
        "duplicate_count": duplicate_count,
    }


def _read_memories(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _terms(text: str) -> list[str]:
    return [match.group(0).lower() for match in TERM_RE.finditer(text)]


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None
