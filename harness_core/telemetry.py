from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def new_chain(root: Path, *, task: str, center: str) -> str:
    """Create a new chain ID for a top-level user query. Returns chain_id."""
    chain_id = uuid.uuid4().hex[:20]
    telemetry_dir = root / ".harness" / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    chain_record = {
        "chain_id":   chain_id,
        "task":       task,
        "center":     center,
        "depth":      0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "spans":      [],
    }
    _chain_path(telemetry_dir, chain_id).write_text(
        json.dumps(chain_record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return chain_id


def begin_span(
    root: Path,
    chain_id: str,
    *,
    tool: str,
    depth: int = 0,
) -> str:
    """Start a span (one tool call). Returns span_id with embedded start_ns."""
    span_id = f"{uuid.uuid4().hex[:12]}:{time.monotonic_ns()}"
    telemetry_dir = root / ".harness" / "telemetry"
    chain = _read_chain(telemetry_dir, chain_id)
    chain["spans"].append({
        "span_id":    span_id,
        "tool":       tool,
        "depth":      depth,
        "start_ns":   time.monotonic_ns(),
        "end_ns":     None,
        "duration_ms": None,
        "tokens_in":  0,
        "tokens_out": 0,
        "status":     "running",
    })
    _write_chain(telemetry_dir, chain_id, chain)
    return span_id


def end_span(
    root: Path,
    chain_id: str,
    span_id: str,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    status: str = "ok",
) -> dict[str, Any]:
    """Close a span and record timing."""
    telemetry_dir = root / ".harness" / "telemetry"
    chain = _read_chain(telemetry_dir, chain_id)
    end_ns = time.monotonic_ns()
    for span in chain["spans"]:
        if span["span_id"] == span_id:
            start_ns = span["start_ns"]
            span["end_ns"]     = end_ns
            span["duration_ms"] = round((end_ns - start_ns) / 1_000_000, 2)
            span["tokens_in"]  = tokens_in
            span["tokens_out"] = tokens_out
            span["status"]     = status
            _write_chain(telemetry_dir, chain_id, chain)
            return span
    return {}


def summarize_chain(root: Path, chain_id: str) -> dict[str, Any]:
    """Return timing + token summary for a chain."""
    telemetry_dir = root / ".harness" / "telemetry"
    chain = _read_chain(telemetry_dir, chain_id)
    spans = [s for s in chain["spans"] if s.get("duration_ms") is not None]
    if not spans:
        return {"chain_id": chain_id, "spans": 0}
    total_ms     = sum(s["duration_ms"] for s in spans)
    total_tokens = sum(s.get("tokens_in", 0) + s.get("tokens_out", 0) for s in spans)
    slowest      = max(spans, key=lambda s: s["duration_ms"])
    return {
        "chain_id":      chain_id,
        "span_count":    len(spans),
        "total_ms":      round(total_ms, 2),
        "avg_ms":        round(total_ms / len(spans), 2),
        "total_tokens":  total_tokens,
        "slowest_tool":  slowest["tool"],
        "slowest_ms":    slowest["duration_ms"],
        "max_depth":     max(s.get("depth", 0) for s in spans),
    }


def recent_telemetry(root: Path, *, limit: int = 10) -> list[dict[str, Any]]:
    """Return summaries for the most recent chains."""
    telemetry_dir = root / ".harness" / "telemetry"
    if not telemetry_dir.exists():
        return []
    files = sorted(telemetry_dir.glob("chain_*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for f in files[:limit]:
        try:
            chain = json.loads(f.read_text(encoding="utf-8"))
            cid = chain.get("chain_id", "")
            results.append(summarize_chain(root, cid))
        except Exception:
            continue
    return results


def _chain_path(telemetry_dir: Path, chain_id: str) -> Path:
    return telemetry_dir / f"chain_{chain_id}.json"


def _read_chain(telemetry_dir: Path, chain_id: str) -> dict[str, Any]:
    p = _chain_path(telemetry_dir, chain_id)
    if not p.exists():
        raise FileNotFoundError(f"chain not found: {chain_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def _write_chain(telemetry_dir: Path, chain_id: str, chain: dict) -> None:
    _chain_path(telemetry_dir, chain_id).write_text(
        json.dumps(chain, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
