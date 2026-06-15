from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_evidence(root: Path, required: list[str], evidence: list[str]) -> dict[str, Any]:
    normalized_evidence = [item.lower() for item in evidence]
    missing = [item for item in required if not _contains_evidence(item, normalized_evidence)]
    return {
        "root": str(root),
        "verdict": "PASS" if not missing else "NEEDS_WORK",
        "missing": missing,
        "evidence": evidence,
    }


def _contains_evidence(required: str, evidence: list[str]) -> bool:
    required_lower = required.lower()
    return any(required_lower in item for item in evidence)
