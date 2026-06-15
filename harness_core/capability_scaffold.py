from __future__ import annotations

import json
from pathlib import Path


def scaffold_capability(root: Path, name: str, description: str) -> dict[str, str]:
    slug = _slug(name)
    skill_dir = root / "capabilities" / slug / "skills" / slug
    tool_dir = root / "capabilities" / slug / "tools"
    skill_dir.mkdir(parents=True, exist_ok=True)
    tool_dir.mkdir(parents=True, exist_ok=True)

    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        f"---\nname: {slug}\ndescription: {description}\n---\n\n# {slug}\n\n{description}\n",
        encoding="utf-8",
    )

    tool_spec_path = tool_dir / "tool-spec.json"
    tool_spec_path.write_text(
        json.dumps(
            {
                "name": slug,
                "description": description,
                "status": "draft",
                "mcp_tools": [],
                "documentation": [],
                "evidence_required": ["tests passed", "usage documented"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"skill_path": str(skill_path), "tool_spec_path": str(tool_spec_path)}


def _slug(name: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in name).split("-") if part)
