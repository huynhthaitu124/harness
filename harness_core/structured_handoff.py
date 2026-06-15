from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_structured_handoff(
    root: Path,
    *,
    title: str,
    summary: str,
    from_center: str,
    to_center: str,
    task_fingerprint: str,
    evidence: list[str],
    context_pack: str | None = None,
    open_items: list[str] | None = None,
) -> dict[str, Any]:
    slug = "".join(character if character.isalnum() else "-" for character in title.lower()).strip("-")[:80]
    handoff_dir = root / "production_artifacts" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = handoff_dir / f"{slug or 'handoff'}.md"
    manifest_path = handoff_dir / f"{slug or 'handoff'}.json"
    manifest = {
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "summary": summary,
        "from_center": from_center,
        "to_center": to_center,
        "task_fingerprint": task_fingerprint,
        "evidence": evidence,
        "context_pack": context_pack,
        "open_items": open_items or [],
        "markdown_path": str(markdown_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(manifest), encoding="utf-8")
    return {"markdown_path": str(markdown_path), "manifest_path": str(manifest_path), "manifest": manifest}


def validate_structured_handoff(manifest_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = root or manifest_path.parents[2]
    missing: list[str] = []
    for field in ("title", "summary", "from_center", "to_center", "task_fingerprint"):
        if not manifest.get(field):
            missing.append(f"missing_field:{field}")
    evidence = manifest.get("evidence", [])
    if not evidence:
        missing.append("missing_evidence")
    for evidence_path in evidence:
        if not (root / evidence_path).exists():
            missing.append(f"missing_evidence_file:{evidence_path}")
    context_pack = manifest.get("context_pack")
    if context_pack and not (root / context_pack).exists():
        missing.append(f"missing_context_pack:{context_pack}")
    return {
        "manifest_path": str(manifest_path),
        "verdict": "PASS" if not missing else "NEEDS_WORK",
        "missing": missing,
        "from_center": manifest.get("from_center"),
        "to_center": manifest.get("to_center"),
        "task_fingerprint": manifest.get("task_fingerprint"),
    }


def _render_markdown(manifest: dict[str, Any]) -> str:
    evidence = "\n".join(f"- `{path}`" for path in manifest["evidence"]) or "- none"
    open_items = "\n".join(f"- {item}" for item in manifest["open_items"]) or "- none"
    context = f"`{manifest['context_pack']}`" if manifest["context_pack"] else "none"
    return (
        f"# {manifest['title']}\n\n"
        f"from: {manifest['from_center']}\n"
        f"to: {manifest['to_center']}\n"
        f"task_fingerprint: {manifest['task_fingerprint']}\n"
        f"context_pack: {context}\n\n"
        f"## Summary\n\n{manifest['summary']}\n\n"
        f"## Evidence\n\n{evidence}\n\n"
        f"## Open Items\n\n{open_items}\n"
    )
