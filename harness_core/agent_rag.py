from __future__ import annotations

import hashlib
import json
import shlex
import time
from pathlib import Path
from typing import Any

from harness_core.context_budget import estimate_tokens, measure_context_savings
from harness_core.contextual_chunks import build_context_locator
from harness_core.hybrid_retrieval import build_hybrid_context_pack
from harness_core.memory_index import build_memory_pack
from harness_core.router import CENTERS, load_state

VALID_CENTERS = (*CENTERS, "auto", "project")


def _cleanup_old_packs(packs_dir: Path, max_age_hours: int = 24) -> None:
    """Delete .md files in packs_dir older than max_age_hours, skipping last-rag-pack.md."""
    if not packs_dir.exists():
        return
    cutoff = time.time() - max_age_hours * 3600
    for f in packs_dir.glob("*.md"):
        if f.name == "last-rag-pack.md":
            continue
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def build_agent_rag_pack(
    root: Path,
    task: str,
    *,
    center: str = "project",
    local_model: str | None = None,
    max_payload_chars: int = 9000,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    if center not in VALID_CENTERS:
        raise ValueError(f"center must be one of: {', '.join(VALID_CENTERS)}")

    state_path = root / ".harness" / "state.json"
    state = load_state(state_path)
    resolved_center = state.get("preferred_center", "auto") if center == "project" else center
    model = local_model or state.get("local_model", {}).get("model") or "qwen3.5:9b"

    memory_path = _memory_path(root)
    sources = []
    parts = []
    locator = build_context_locator(root, task, top_k=8)
    if memory_path.exists():
        memory_pack = build_memory_pack(memory_path, task, top_k=5, max_chars=max_payload_chars // 3)
        if memory_pack.strip():
            parts.append(memory_pack)
            sources.append("memory_pack")

    hybrid_pack = build_hybrid_context_pack(root, task, top_k=5)
    if hybrid_pack.strip():
        parts.append(hybrid_pack)
        sources.append("hybrid_rag")

    payload = _trim("\n\n".join(parts), max_payload_chars)

    packs_dir = root / ".harness" / "context_packs"
    if ticket_id:
        filename = f"{ticket_id}.md"
    else:
        task_hash = hashlib.md5(task.encode()).hexdigest()[:8]
        filename = f"pack-{task_hash}.md"
    out_path = packs_dir / filename
    _cleanup_old_packs(packs_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    commands = _agent_commands(out_path, task, model)
    pack_text = render_agent_rag_pack(
        root=root,
        task=task,
        center=resolved_center,
        local_model=model,
        context_pack_path=out_path,
        sources=sources,
        payload=payload,
        locator=locator,
        commands=commands,
    )
    out_path.write_text(pack_text, encoding="utf-8")

    # Update last-rag-pack.md symlink to point to the new file
    symlink_path = packs_dir / "last-rag-pack.md"
    if symlink_path.exists() or symlink_path.is_symlink():
        symlink_path.unlink()
    symlink_path.symlink_to(out_path.name)

    savings = measure_context_savings(root, payload)
    return {
        "verdict": "PASS" if payload.strip() else "NEEDS_WORK",
        "root": str(root),
        "task": task,
        "center": resolved_center,
        "sources": sources,
        "local_model": model,
        "context_pack_path": str(out_path),
        "payload_tokens_estimate": estimate_tokens(payload),
        "locator": locator,
        "raw_tokens_estimate": savings["raw_tokens"],
        "estimated_savings_percent": savings["savings_percent"],
        "commands": commands,
    }


def render_agent_rag_pack(
    *,
    root: Path,
    task: str,
    center: str,
    local_model: str,
    context_pack_path: Path,
    sources: list[str],
    payload: str,
    locator: dict[str, Any],
    commands: dict[str, str],
) -> str:
    rel_path = _display_path(root, context_pack_path)
    command_lines = "\n".join(f"# {name}\n{command}" for name, command in commands.items())
    locator_text = json.dumps(locator, indent=2, ensure_ascii=False)
    return "\n".join(
        [
            "# Harness Shared RAG Pack",
            "",
            f"task: {task}",
            f"root: {root}",
            f"path: {rel_path}",
            f"center: {center}",
            f"source: {', '.join(sources) if sources else 'none'}",
            f"local_model: {local_model}",
            "",
            "## Grounding Policy",
            "",
            "This pack is a navigation aid, not source of truth. Before editing, read the real target files and tests listed by the locator. Extra grep/read is expected when it answers a specific verification question.",
            "",
            "## Locator",
            "",
            "```json",
            locator_text,
            "```",
            "",
            "## Agent Commands",
            "",
            "All centers should consume this same context pack before reasoning over the repo.",
            "",
            "```bash",
            command_lines,
            "```",
            "",
            "## Retrieval Payload",
            "",
            "```text",
            payload.strip(),
            "```",
            "",
        ]
    )


def _agent_commands(pack_path: Path, task: str, local_model: str) -> dict[str, str]:
    prefix = f"PACK={shlex.quote(str(pack_path))}; TASK={shlex.quote(task)};"
    prompt_expr = '"$(printf \'%s\\n\\nTask: %s\' "$(cat "$PACK")" "$TASK")"'
    local_prefix = f"{prefix} MODEL={shlex.quote(local_model)}; export PACK TASK MODEL;"
    return {
        "codex": f"{prefix} codex exec {prompt_expr}",
        "claude": f"{prefix} claude -p {prompt_expr} --model sonnet",
        "antigravity": f"{prefix} agy --print {prompt_expr}",
        "local": (
            f"{local_prefix} python3 -c "
            + shlex.quote(
                "import json, os, pathlib, urllib.request; "
                "pack=pathlib.Path(os.environ['PACK']).read_text(); "
                "payload={'model': os.environ['MODEL'], 'messages': [{'role': 'user', 'content': pack + '\\n\\nTask: ' + os.environ['TASK']}], 'stream': False, 'think': False}; "
                "req=urllib.request.Request('http://localhost:11434/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}); "
                "print(urllib.request.urlopen(req, timeout=120).read().decode())"
            )
        ),
        "refresh": f"harness rag-pack {shlex.quote(task)}",
    }


def _memory_path(root: Path) -> Path:
    project_memory = root / ".harness" / "memory.jsonl"
    if project_memory.exists():
        return project_memory
    return root / "production_artifacts" / "memory.jsonl"


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 90)].rstrip() + "\n\n[truncated by harness agent RAG pack]"
