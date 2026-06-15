from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Four failure categories from arxiv 2605.15221
FAILURE_CATEGORIES = {
    "action_realization":    "agent planned correctly but could not execute the action",
    "environment_contract":  "environment behaved differently than agent expected",
    "trajectory_degeneration": "agent got stuck in a loop or repeated failed steps",
    "residual_reasoning":    "agent reasoning was flawed from the start",
}


def begin_trajectory(root: Path, *, center: str, model: str, task: str) -> str:
    """Start a new trajectory session. Returns session_id."""
    session_id = uuid.uuid4().hex[:16]
    traj_dir = root / ".harness" / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "session_id": session_id,
        "center": center,
        "model": model,
        "task": task,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": [],
        "outcome": None,
        "failure_step": None,
        "failure_category": None,
    }
    _write_traj(traj_dir, session_id, record)
    return session_id


def record_step(
    root: Path,
    session_id: str,
    *,
    tool: str,
    args_hash: str | None = None,
    result_status: str,
    duration_ms: int = 0,
    tokens: int = 0,
    note: str = "",
) -> dict[str, Any]:
    """Append one tool-call step to an existing trajectory."""
    traj_dir = root / ".harness" / "trajectories"
    record = _read_traj(traj_dir, session_id)
    step = {
        "index":         len(record["steps"]),
        "tool":          tool,
        "args_hash":     args_hash,
        "result_status": result_status,
        "duration_ms":   duration_ms,
        "tokens":        tokens,
        "note":          note,
        "ts":            datetime.now(timezone.utc).isoformat(),
    }
    record["steps"].append(step)
    _write_traj(traj_dir, session_id, record)
    return step


def end_trajectory(
    root: Path,
    session_id: str,
    *,
    outcome: str,
    failure_step: int | None = None,
) -> dict[str, Any]:
    """Close a trajectory. outcome: 'success' | 'failure' | 'partial'."""
    traj_dir = root / ".harness" / "trajectories"
    record = _read_traj(traj_dir, session_id)
    record["outcome"] = outcome
    record["ended_at"] = datetime.now(timezone.utc).isoformat()
    record["failure_step"] = failure_step
    if outcome == "failure" and record["steps"]:
        idx = failure_step if failure_step is not None else len(record["steps"]) - 1
        record["failure_category"] = classify_failure(record["steps"], failed_at=idx)
    _write_traj(traj_dir, session_id, record)
    return record


def classify_failure(steps: list[dict], *, failed_at: int) -> str:
    """Heuristically classify failure into one of the 4 categories."""
    if not steps:
        return "residual_reasoning"

    failed_step = steps[failed_at] if failed_at < len(steps) else steps[-1]
    tool = failed_step.get("tool", "")
    status = failed_step.get("result_status", "")

    # Trajectory degeneration: same tool called ≥3 times in last 5 steps
    recent = steps[max(0, failed_at - 4): failed_at + 1]
    tool_counts = {}
    for s in recent:
        tool_counts[s.get("tool", "")] = tool_counts.get(s.get("tool", ""), 0) + 1
    if max(tool_counts.values(), default=0) >= 3:
        return "trajectory_degeneration"

    # Environment contract: env-level errors (filesystem, network, shell)
    env_signals = ("permission", "not found", "timeout", "connection", "eacces", "enoent")
    note = failed_step.get("note", "").lower()
    if any(sig in note for sig in env_signals) or status in ("env_error", "timeout"):
        return "environment_contract"

    # Action realization: agent planned right but tool execution failed
    if status in ("tool_error", "exec_error", "not_implemented"):
        return "action_realization"

    # Default: reasoning failure
    return "residual_reasoning"


def list_trajectories(root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    """List recent trajectories, most recent first."""
    traj_dir = root / ".harness" / "trajectories"
    if not traj_dir.exists():
        return []
    files = sorted(traj_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for f in files[:limit]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "session_id":       d.get("session_id"),
                "center":           d.get("center"),
                "model":            d.get("model"),
                "outcome":          d.get("outcome"),
                "failure_category": d.get("failure_category"),
                "steps":            len(d.get("steps", [])),
                "started_at":       d.get("started_at"),
            })
        except Exception:
            continue
    return results


def _write_traj(traj_dir: Path, session_id: str, record: dict) -> None:
    path = traj_dir / f"{session_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_traj(traj_dir: Path, session_id: str) -> dict[str, Any]:
    path = traj_dir / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"trajectory not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))
