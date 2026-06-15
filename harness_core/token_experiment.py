from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VARIANTS = {"baseline", "harness"}
DEFAULT_CENTERS = ("codex", "claude")


def record_experiment_run(
    path: Path,
    *,
    experiment_id: str,
    task_fingerprint: str,
    center: str,
    variant: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float = 0.0,
    success: bool = True,
    quality_score: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError("variant must be baseline or harness")
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_id,
        "task_fingerprint": task_fingerprint,
        "center": center,
        "variant": variant,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cost_usd": float(cost_usd),
        "success": bool(success),
        "quality_score": quality_score,
        "metadata": metadata or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def summarize_experiments(path: Path, *, quality_tolerance: float = 0.05) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                grouped.setdefault(entry["experiment_id"], []).append(entry)

    valid_pairs: list[dict[str, Any]] = []
    invalid_pairs: list[dict[str, Any]] = []
    for experiment_id, entries in sorted(grouped.items()):
        pair, reasons = _validate_pair(entries, quality_tolerance)
        if reasons:
            invalid_pairs.append({"experiment_id": experiment_id, "reasons": reasons})
            continue
        baseline = pair["baseline"]
        harness = pair["harness"]
        baseline_tokens = baseline["input_tokens"] + baseline["output_tokens"]
        harness_tokens = harness["input_tokens"] + harness["output_tokens"]
        token_savings = ((baseline_tokens - harness_tokens) / baseline_tokens) * 100
        cost_savings = None
        if baseline["cost_usd"] > 0:
            cost_savings = ((baseline["cost_usd"] - harness["cost_usd"]) / baseline["cost_usd"]) * 100
        valid_pairs.append(
            {
                "experiment_id": experiment_id,
                "task_fingerprint": baseline["task_fingerprint"],
                "center": baseline["center"],
                "baseline_tokens": baseline_tokens,
                "harness_tokens": harness_tokens,
                "token_savings_percent": round(token_savings, 2),
                "cost_savings_percent": None if cost_savings is None else round(cost_savings, 2),
            }
        )

    return {
        "path": str(path),
        "valid_pair_count": len(valid_pairs),
        "invalid_pair_count": len(invalid_pairs),
        "pairs": valid_pairs,
        "invalid_pairs": invalid_pairs,
        "by_center": _summarize_by_center(valid_pairs),
    }


def evaluate_token_evidence(
    report: dict[str, Any], *, required_centers: tuple[str, ...] = DEFAULT_CENTERS
) -> dict[str, Any]:
    by_center = report.get("by_center", {})
    missing_centers = sorted(center for center in required_centers if int(by_center.get(center, {}).get("pair_count", 0)) < 1)
    non_saving_centers = sorted(
        center
        for center in required_centers
        if center in by_center and float(by_center[center].get("average_token_savings_percent", 0)) <= 0
    )
    if non_saving_centers:
        verdict = "REGRESSION"
    elif missing_centers:
        verdict = "INCOMPLETE"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "valid_pair_count": int(report.get("valid_pair_count", 0)),
        "invalid_pair_count": int(report.get("invalid_pair_count", 0)),
        "missing_centers": missing_centers,
        "non_saving_centers": non_saving_centers,
        "by_center": by_center,
    }


def ingest_claude_result(
    path: Path,
    raw_json: str,
    *,
    experiment_id: str,
    task_fingerprint: str,
    variant: str,
    quality_score: float | None = None,
) -> dict[str, Any]:
    payload = _claude_payload(raw_json)
    usage = payload.get("usage", {})
    input_tokens = sum(
        int(usage.get(key, 0))
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    return record_experiment_run(
        path,
        experiment_id=experiment_id,
        task_fingerprint=task_fingerprint,
        center="claude",
        variant=variant,
        input_tokens=input_tokens,
        output_tokens=int(usage.get("output_tokens", 0)),
        cost_usd=float(payload.get("total_cost_usd", 0.0)),
        success=not bool(payload.get("is_error", False)),
        quality_score=quality_score,
        metadata={"source": "claude-json"},
    )


def ingest_codex_jsonl(
    path: Path,
    raw_jsonl: str,
    *,
    experiment_id: str,
    task_fingerprint: str,
    variant: str,
    quality_score: float | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for line in raw_jsonl.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    usage = None
    for event in events:
        found = _find_usage(event)
        if found is not None:
            usage = found
    if usage is None:
        raise ValueError("Codex JSONL contains no token usage event")

    input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)))
    output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)))
    cached_input_tokens = int(usage.get("cached_input_tokens", 0))
    failed = any(event.get("type") in {"error", "turn.failed"} for event in events)
    return record_experiment_run(
        path,
        experiment_id=experiment_id,
        task_fingerprint=task_fingerprint,
        center="codex",
        variant=variant,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        success=not failed,
        quality_score=quality_score,
        metadata={"source": "codex-jsonl", "cached_input_tokens": cached_input_tokens},
    )


def _validate_pair(entries: list[dict[str, Any]], quality_tolerance: float) -> tuple[dict[str, dict[str, Any]], list[str]]:
    reasons: list[str] = []
    pair: dict[str, dict[str, Any]] = {}
    for entry in entries:
        variant = entry.get("variant")
        if variant in pair:
            reasons.append(f"duplicate_{variant}")
        elif variant in VARIANTS:
            pair[variant] = entry
    if set(pair) != VARIANTS:
        reasons.append("missing_baseline_or_harness")
        return pair, reasons

    baseline = pair["baseline"]
    harness = pair["harness"]
    if baseline["task_fingerprint"] != harness["task_fingerprint"]:
        reasons.append("task_fingerprint_mismatch")
    if baseline["center"] != harness["center"]:
        reasons.append("center_mismatch")
    if not baseline.get("success", True) or not harness.get("success", True):
        reasons.append("failed_run")
    if baseline["input_tokens"] + baseline["output_tokens"] <= 0:
        reasons.append("zero_baseline_tokens")
    baseline_quality = baseline.get("quality_score")
    harness_quality = harness.get("quality_score")
    if baseline_quality is not None and harness_quality is not None:
        if float(harness_quality) + quality_tolerance < float(baseline_quality):
            reasons.append("quality_regression")
    return pair, reasons


def _summarize_by_center(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = {}
    for pair in pairs:
        buckets.setdefault(pair["center"], []).append(pair["token_savings_percent"])
    return {
        center: {"pair_count": len(values), "average_token_savings_percent": round(sum(values) / len(values), 2)}
        for center, values in sorted(buckets.items())
    }


def _claude_payload(raw_json: str) -> dict[str, Any]:
    payload = json.loads(raw_json)
    if isinstance(payload, dict) and isinstance(payload.get("stdout"), str):
        lines = [line for line in payload["stdout"].splitlines() if line.strip()]
        if lines:
            return json.loads(lines[-1])
    if not isinstance(payload, dict):
        raise ValueError("Claude result must be a JSON object")
    return payload


def _find_usage(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        for key in ("usage", "token_usage"):
            candidate = value.get(key)
            if isinstance(candidate, dict) and any(
                token_key in candidate for token_key in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens")
            ):
                return candidate
        for child in value.values():
            found = _find_usage(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_usage(child)
            if found is not None:
                return found
    return None
