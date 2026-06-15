from __future__ import annotations

from pathlib import Path
from typing import Any


def audit_context_packs(root: Path, *, max_chars_per_pack: int = 12000) -> dict[str, Any]:
    pack_dir = root / "production_artifacts" / "context_packs"
    failures: list[str] = []
    warnings: list[str] = []
    packs: list[dict[str, Any]] = []
    if not pack_dir.exists():
        return {"verdict": "PASS", "failures": [], "warnings": ["context_pack_dir_missing"], "pack_count": 0, "packs": []}

    for path in sorted(pack_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(pack_dir).as_posix()
        char_count = len(text)
        has_heading = "\n## " in f"\n{text}"
        has_fence = "```" in text
        has_provenance = "lines:" in text or "\npath:" in f"\n{text}" or _has_path_heading(text)
        if char_count > max_chars_per_pack:
            failures.append(f"over_budget:{rel}")
        if not has_heading:
            failures.append(f"missing_section_heading:{rel}")
        if not has_fence:
            failures.append(f"missing_code_fence:{rel}")
        if not has_provenance:
            failures.append(f"missing_provenance:{rel}")
        packs.append(
            {
                "path": str(path),
                "chars": char_count,
                "has_heading": has_heading,
                "has_code_fence": has_fence,
                "has_provenance": has_provenance,
            }
        )

    return {
        "verdict": "PASS" if not failures else "NEEDS_WORK",
        "failures": failures,
        "warnings": warnings,
        "pack_count": len(packs),
        "max_chars_per_pack": max_chars_per_pack,
        "packs": packs,
    }


def _has_path_heading(text: str) -> bool:
    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        heading = line[3:].strip()
        if "/" in heading or "." in Path(heading).name:
            return True
    return False
