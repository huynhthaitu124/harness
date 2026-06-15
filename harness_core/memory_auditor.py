from __future__ import annotations

from pathlib import Path
from typing import Any

EVIDENCE_MARKERS = ("evidence:", "tests passed", "verdict", "pass", "usage", "benchmark")


def audit_handoffs(root: Path) -> dict[str, Any]:
    handoff_dir = root / "production_artifacts" / "handoffs"
    issues = []
    if not handoff_dir.exists():
        return {"root": str(root), "issue_count": 0, "issues": []}
    for path in sorted(handoff_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if not any(marker in text for marker in EVIDENCE_MARKERS):
            issues.append(
                {
                    "path": str(path),
                    "type": "missing_evidence",
                    "message": "Handoff does not include explicit evidence markers.",
                }
            )
    return {"root": str(root), "issue_count": len(issues), "issues": issues}
