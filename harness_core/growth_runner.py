from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_core.evaluator import evaluate_evidence
from harness_core.self_growth import run_growth_cycle
from harness_core.token_ledger import record_usage


def run_evaluated_growth_cycle(
    root: Path,
    *,
    topic: str,
    sources: list[dict[str, str]],
    actions: list[str],
    usage: dict[str, Any],
    required_evidence: list[str],
) -> dict[str, Any]:
    cycle = run_growth_cycle(root, topic=topic, sources=sources, actions=actions)
    ledger = root / "production_artifacts" / "usage.jsonl"
    record_usage(
        ledger,
        center=usage["center"],
        input_tokens=int(usage["input_tokens"]),
        output_tokens=int(usage["output_tokens"]),
        cost_usd=float(usage["cost_usd"]),
        label=f"growth:{topic}",
    )
    evidence = ["cycle recorded", "usage recorded"]
    if actions:
        evidence.append("actions proposed")
    evaluation = evaluate_evidence(root, required_evidence, evidence)
    return {"cycle": cycle, "ledger": str(ledger), "evaluation": evaluation}
