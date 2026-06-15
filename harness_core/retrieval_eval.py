from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from harness_core.hybrid_retrieval import retrieve_hybrid_chunks

Retriever = Callable[[str, int], list[dict[str, Any]]]


def evaluate_retrieval(
    cases: list[dict[str, Any]],
    *,
    retriever: Retriever,
    top_k: int,
    min_recall: float = 0.8,
    min_mrr: float = 0.5,
) -> dict[str, Any]:
    if not cases:
        return {
            "verdict": "NEEDS_WORK",
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "case_count": 0,
            "reasons": ["no_cases"],
            "cases": [],
        }

    results = []
    recalls = []
    reciprocal_ranks = []
    for case in cases:
        expected = list(dict.fromkeys(case.get("expected_paths", [])))
        retrieved = retriever(case["query"], top_k)[:top_k]
        paths = [item["path"] for item in retrieved]
        hits = [path for path in expected if path in paths]
        recall = len(hits) / len(expected) if expected else 0.0
        reciprocal_rank = 0.0
        for rank, path in enumerate(paths, start=1):
            if path in expected:
                reciprocal_rank = 1.0 / rank
                break
        recalls.append(recall)
        reciprocal_ranks.append(reciprocal_rank)
        results.append(
            {
                "id": case.get("id", case["query"]),
                "query": case["query"],
                "expected_paths": expected,
                "retrieved_paths": paths,
                "recall_at_k": round(recall, 4),
                "reciprocal_rank": round(reciprocal_rank, 4),
                "passes": bool(expected) and recall > 0,
            }
        )

    recall_at_k = sum(recalls) / len(recalls)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    reasons = []
    if recall_at_k < min_recall:
        reasons.append("recall_below_threshold")
    if mrr < min_mrr:
        reasons.append("mrr_below_threshold")
    return {
        "verdict": "PASS" if not reasons else "NEEDS_WORK",
        "top_k": top_k,
        "case_count": len(cases),
        "recall_at_k": round(recall_at_k, 4),
        "mrr": round(mrr, 4),
        "min_recall": min_recall,
        "min_mrr": min_mrr,
        "reasons": reasons,
        "cases": results,
    }


def evaluate_hybrid_dataset(
    root: Path,
    dataset_path: Path,
    *,
    top_k: int = 5,
    min_recall: float = 0.8,
    min_mrr: float = 0.5,
) -> dict[str, Any]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    return evaluate_retrieval(
        dataset.get("cases", []),
        retriever=lambda query, limit: retrieve_hybrid_chunks(root, query, top_k=limit),
        top_k=top_k,
        min_recall=min_recall,
        min_mrr=min_mrr,
    )
