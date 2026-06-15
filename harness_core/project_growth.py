"""Per-project self-growth system.

Each initialized project gets its own growth state under .harness/growth/:
  - feature_progress.json   — project-specific feature tracker
  - routing_evidence.jsonl  — which routing decisions worked for this project
  - pattern_db.jsonl        — successful solution patterns (autonomous memory)
  - experiment_queue.json   — experiments queued for this project

Patterns are extracted automatically from successful trajectories.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def bootstrap_growth(root: Path, initial_features: list[str]) -> dict[str, Any]:
    """Called during `harness init`. Creates .harness/growth/ with starter data."""
    growth_dir = root / ".harness" / "growth"
    growth_dir.mkdir(parents=True, exist_ok=True)

    # Feature progress (project-specific copy)
    fp_path = growth_dir / "feature_progress.json"
    if not fp_path.exists():
        fp_path.write_text(
            json.dumps({
                "project": root.name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "features": [
                    {"id": f"feat_{i}", "title": f, "status": "pending", "evidence": []}
                    for i, f in enumerate(initial_features)
                ],
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # Routing evidence log (empty — fills as agents use harness)
    ev_path = growth_dir / "routing_evidence.jsonl"
    if not ev_path.exists():
        ev_path.write_text("", encoding="utf-8")

    # Pattern database (empty — fills from successful trajectories)
    pd_path = growth_dir / "pattern_db.jsonl"
    if not pd_path.exists():
        pd_path.write_text("", encoding="utf-8")

    # Seed 3 baseline experiments
    eq_path = growth_dir / "experiment_queue.json"
    if not eq_path.exists():
        eq_path.write_text(
            json.dumps({
                "project": root.name,
                "experiments": [
                    {
                        "id":          "baseline_routing",
                        "title":       "Baseline routing accuracy",
                        "description": "Measure which center gets assigned most tasks and whether outcomes match",
                        "status":      "queued",
                        "queued_at":   datetime.now(timezone.utc).isoformat(),
                    },
                    {
                        "id":          "baseline_context_compression",
                        "title":       "Context compression savings",
                        "description": "Compare token usage with vs without context pack on 5 typical queries",
                        "status":      "queued",
                        "queued_at":   datetime.now(timezone.utc).isoformat(),
                    },
                    {
                        "id":          "baseline_rag_recall",
                        "title":       "RAG recall on project-specific queries",
                        "description": "Test BM25 and semantic index recall against 10 known-answer questions",
                        "status":      "queued",
                        "queued_at":   datetime.now(timezone.utc).isoformat(),
                    },
                ],
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return {
        "growth_dir":        str(growth_dir),
        "feature_progress":  str(fp_path),
        "routing_evidence":  str(ev_path),
        "pattern_db":        str(pd_path),
        "experiment_queue":  str(eq_path),
    }


# ── Pattern extraction from trajectories ─────────────────────────────────────

def extract_pattern_from_trajectory(
    root: Path,
    trajectory: dict[str, Any],
) -> dict[str, Any] | None:
    """Auto-extract a reusable pattern from a successful trajectory."""
    if trajectory.get("outcome") != "success":
        return None
    steps = trajectory.get("steps", [])
    if not steps:
        return None

    tool_sequence = [s["tool"] for s in steps if s.get("result_status") == "ok"]
    if not tool_sequence:
        return None

    pattern = {
        "id":            uuid.uuid4().hex[:12],
        "source":        "trajectory",
        "session_id":    trajectory.get("session_id"),
        "center":        trajectory.get("center"),
        "model":         trajectory.get("model"),
        "task_snippet":  (trajectory.get("task") or "")[:120],
        "tool_sequence": tool_sequence,
        "step_count":    len(steps),
        "extracted_at":  datetime.now(timezone.utc).isoformat(),
        "use_count":     0,
    }

    _append_pattern(root, pattern)
    return pattern


def _append_pattern(root: Path, pattern: dict[str, Any]) -> None:
    pd_path = root / ".harness" / "growth" / "pattern_db.jsonl"
    pd_path.parent.mkdir(parents=True, exist_ok=True)
    with pd_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(pattern, ensure_ascii=False) + "\n")


# ── Routing evidence ──────────────────────────────────────────────────────────

def record_routing_evidence(
    root: Path,
    *,
    center: str,
    task_type: str,
    outcome: str,
    model_tier: str = "",
    duration_ms: int = 0,
) -> None:
    ev_path = root / ".harness" / "growth" / "routing_evidence.jsonl"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts":          datetime.now(timezone.utc).isoformat(),
        "center":      center,
        "task_type":   task_type,
        "outcome":     outcome,
        "model_tier":  model_tier,
        "duration_ms": duration_ms,
    }
    with ev_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Status + next action ──────────────────────────────────────────────────────

def growth_status(root: Path) -> dict[str, Any]:
    growth_dir = root / ".harness" / "growth"
    if not growth_dir.exists():
        return {"initialized": False}

    # Feature progress
    fp = {}
    fp_path = growth_dir / "feature_progress.json"
    if fp_path.exists():
        data = json.loads(fp_path.read_text(encoding="utf-8"))
        feats = data.get("features", [])
        done  = sum(1 for f in feats if f.get("status") == "done")
        fp    = {"total": len(feats), "done": done, "pending": len(feats) - done}

    # Pattern count
    pd_path = growth_dir / "pattern_db.jsonl"
    patterns = 0
    if pd_path.exists():
        patterns = sum(1 for line in pd_path.read_text(encoding="utf-8").splitlines() if line.strip())

    # Routing evidence summary
    ev_path = growth_dir / "routing_evidence.jsonl"
    evidence_count = 0
    center_outcomes: dict[str, dict[str, int]] = {}
    if ev_path.exists():
        for line in ev_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            evidence_count += 1
            rec = json.loads(line)
            c = rec.get("center", "unknown")
            o = rec.get("outcome", "unknown")
            center_outcomes.setdefault(c, {})
            center_outcomes[c][o] = center_outcomes[c].get(o, 0) + 1

    # Experiment queue
    eq_path = growth_dir / "experiment_queue.json"
    experiments = {"queued": 0, "running": 0, "done": 0}
    if eq_path.exists():
        for exp in json.loads(eq_path.read_text(encoding="utf-8")).get("experiments", []):
            st = exp.get("status", "queued")
            experiments[st] = experiments.get(st, 0) + 1

    return {
        "initialized":     True,
        "feature_progress": fp,
        "pattern_count":   patterns,
        "evidence_count":  evidence_count,
        "center_outcomes": center_outcomes,
        "experiments":     experiments,
    }


def next_project_action(root: Path) -> dict[str, Any]:
    """Return the highest-priority growth action for this project."""
    status = growth_status(root)
    if not status.get("initialized"):
        return {"action": "init", "reason": "project not initialized with harness"}

    # Not enough routing evidence → suggest running a task to collect data
    if status.get("evidence_count", 0) < 5:
        return {
            "action": "collect_evidence",
            "reason": "fewer than 5 routing decisions recorded — run some tasks first",
        }

    # Queued experiments waiting
    exps = status.get("experiments", {})
    if exps.get("queued", 0) > 0:
        eq_path = root / ".harness" / "growth" / "experiment_queue.json"
        data    = json.loads(eq_path.read_text(encoding="utf-8"))
        queued  = [e for e in data["experiments"] if e.get("status") == "queued"]
        if queued:
            return {
                "action":      "run_experiment",
                "experiment":  queued[0],
                "reason":      f"{len(queued)} experiment(s) queued",
            }

    # Pending features
    fp = status.get("feature_progress", {})
    if fp.get("pending", 0) > 0:
        return {
            "action": "implement_feature",
            "reason": f"{fp['pending']} features still pending",
        }

    return {"action": "idle", "reason": "all queued work complete — add new experiments or features"}


def search_patterns(root: Path, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
    """Return patterns whose task_snippet or tool_sequence matches the query."""
    pd_path = root / ".harness" / "growth" / "pattern_db.jsonl"
    if not pd_path.exists():
        return []
    query_lower = query.lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for line in pd_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        score = 0
        if query_lower in (p.get("task_snippet") or "").lower():
            score += 3
        for tool in p.get("tool_sequence", []):
            if query_lower in tool.lower():
                score += 1
        if score:
            scored.append((score, p))
    return [p for _, p in sorted(scored, key=lambda x: -x[0])[:top_k]]
