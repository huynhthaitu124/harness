from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_experiment_output(root: Path, output: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    failures: list[str] = []
    checks = {"summary": False, "citation_count": False, "citations": False, "risks": False}

    summary = output.get("summary")
    word_count = len(summary.split()) if isinstance(summary, str) else 0
    if isinstance(summary, str) and summary.strip() and word_count <= 250:
        checks["summary"] = True
    else:
        failures.append(f"summary_word_count:{word_count}")

    citations = output.get("citations")
    if isinstance(citations, list) and len(citations) == 5:
        checks["citation_count"] = True
    else:
        failures.append(f"citation_count:{len(citations) if isinstance(citations, list) else 0}")

    citations_valid = isinstance(citations, list) and len(set(citations)) == len(citations)
    if isinstance(citations, list):
        if len(set(citations)) != len(citations):
            failures.append("duplicate_citations")
        for citation in citations:
            if not isinstance(citation, str):
                failures.append("citation_not_string")
                citations_valid = False
                continue
            candidate = (root / citation).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                failures.append(f"citation_outside_root:{citation}")
                citations_valid = False
                continue
            if not candidate.is_file():
                failures.append(f"citation_missing:{citation}")
                citations_valid = False
    else:
        citations_valid = False
    checks["citations"] = citations_valid

    risks = output.get("risks")
    if isinstance(risks, list) and len(risks) == 3 and all(isinstance(risk, str) and risk.strip() for risk in risks):
        checks["risks"] = True
    else:
        failures.append(f"risk_count:{len(risks) if isinstance(risks, list) else 0}")

    quality_score = round(sum(checks.values()) / len(checks), 2)
    return {
        "verdict": "PASS" if not failures else "NEEDS_WORK",
        "quality_score": quality_score,
        "checks": checks,
        "failures": failures,
        "metrics": {"summary_word_count": word_count},
    }
