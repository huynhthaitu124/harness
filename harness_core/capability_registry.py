from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def list_capabilities(root: Path) -> list[dict[str, Any]]:
    capabilities_root = root / "capabilities"
    if not capabilities_root.exists():
        return []
    items = []
    for capability in sorted(path for path in capabilities_root.iterdir() if path.is_dir()):
        spec_path = capability / "tools" / "tool-spec.json"
        spec = {}
        if spec_path.exists():
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        items.append(
            {
                "name": capability.name,
                "description": spec.get("description", ""),
                "status": spec.get("status", "unknown"),
                "skill_path": str(capability / "skills" / capability.name / "SKILL.md"),
                "tool_spec_path": str(spec_path),
            }
        )
    return items


def evaluate_capability(root: Path, name: str, *, evidence: list[str]) -> dict[str, Any]:
    capability = root / "capabilities" / name
    skill_path = capability / "skills" / name / "SKILL.md"
    spec_path = capability / "tools" / "tool-spec.json"
    missing: list[str] = []
    if not skill_path.exists():
        missing.append("missing_skill")
    if not spec_path.exists():
        missing.append("missing_tool_spec")
        spec: dict[str, Any] = {}
    else:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not spec.get("mcp_tools"):
        missing.append("missing_mcp_tools")
    documentation = spec.get("documentation", [])
    if not documentation:
        missing.append("missing_documentation")
    for path in documentation:
        if not (root / path).exists():
            missing.append(f"missing_documentation_file:{path}")
    if not evidence:
        missing.append("missing_evidence")
    for path in evidence:
        if not (root / path).exists():
            missing.append(f"missing_evidence_file:{path}")
    return {
        "name": name,
        "verdict": "PASS" if not missing else "NEEDS_WORK",
        "missing": missing,
        "skill_path": str(skill_path),
        "tool_spec_path": str(spec_path),
        "mcp_tools": spec.get("mcp_tools", []),
        "documentation": documentation,
        "evidence": evidence,
    }


def promote_capability(root: Path, name: str, *, evidence: list[str]) -> dict[str, Any]:
    report = evaluate_capability(root, name, evidence=evidence)
    if report["verdict"] != "PASS":
        return {**report, "status": "draft"}
    spec_path = Path(report["tool_spec_path"])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["status"] = "active"
    spec["promoted_at"] = datetime.now(timezone.utc).isoformat()
    spec["promotion_evidence"] = evidence
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**report, "status": "active", "promoted_at": spec["promoted_at"]}
