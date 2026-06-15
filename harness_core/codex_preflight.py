from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from harness_core.context_budget import estimate_tokens, iter_text_files
from harness_core.hybrid_retrieval import build_hybrid_context_pack
from harness_core.memory_index import build_memory_pack

LocalDistiller = Callable[[str, str], dict[str, Any]]


def build_codex_preflight(
    root: Path,
    task: str,
    *,
    memory_path: Path,
    max_codex_chars: int = 6000,
    local_distiller: LocalDistiller | None = None,
) -> dict[str, Any]:
    raw_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in iter_text_files(root))
    raw_tokens = estimate_tokens(raw_text)
    stages = ["memory_pack", "hybrid_rag"]
    memory_pack = build_memory_pack(memory_path, task, top_k=5, max_chars=max_codex_chars // 2) if memory_path.exists() else ""
    rag_pack = build_hybrid_context_pack(root, task, top_k=4)
    compact_context = _trim("\n\n".join(part for part in (memory_pack, rag_pack) if part.strip()), max_codex_chars)
    local_usage = None
    local_distill_warning = None
    if local_distiller is not None:
        distilled = local_distiller(compact_context, task)
        distilled_context = str(distilled.get("context", "")).strip()
        if distilled_context:
            unsafe_reason = _unsafe_local_distill_reason(distilled_context)
            if unsafe_reason:
                local_distill_warning = unsafe_reason
                stages.append("local_qwen_distill_rejected")
            else:
                compact_context = _trim(distilled_context, max_codex_chars)
                stages.append("local_qwen_distill")
        usage = distilled.get("usage", {})
        local_usage = {
            "prompt_eval_count": int(usage.get("prompt_eval_count", 0)),
            "eval_count": int(usage.get("eval_count", 0)),
        }
        local_usage["total_tokens"] = local_usage["prompt_eval_count"] + local_usage["eval_count"]

    payload_tokens = estimate_tokens(compact_context)
    reduction = 0.0 if raw_tokens == 0 else max(0.0, (raw_tokens - payload_tokens) / raw_tokens * 100)
    return {
        "verdict": "PASS" if compact_context else "NEEDS_WORK",
        "must_use_before_codex": True,
        "task": task,
        "stages": stages,
        "raw_tokens_estimate": raw_tokens,
        "codex_payload_tokens_estimate": payload_tokens,
        "estimated_codex_input_reduction_percent": round(reduction, 2),
        "codex_payload_chars": len(compact_context),
        "max_codex_chars": max_codex_chars,
        "codex_payload": compact_context,
        "local_usage": local_usage,
        "local_distill_warning": local_distill_warning,
    }


def render_codex_preflight_context_pack(report: dict[str, Any], *, root: Path, context_pack_path: Path) -> str:
    payload = str(report.get("codex_payload", "")).strip()
    try:
        display_path = context_pack_path.relative_to(root)
    except ValueError:
        display_path = context_pack_path
    stages = [str(stage) for stage in report.get("stages", [])]
    return "\n".join(
        [
            "# Codex Preflight Context Pack",
            "",
            f"task: {report.get('task', '')}",
            f"root: {root}",
            f"path: {display_path}",
            f"source: {', '.join(stages)}",
            f"raw_tokens_estimate: {report.get('raw_tokens_estimate', 0)}",
            f"codex_payload_tokens_estimate: {report.get('codex_payload_tokens_estimate', 0)}",
            f"estimated_codex_input_reduction_percent: {report.get('estimated_codex_input_reduction_percent', 0)}",
            "",
            "## Distilled Payload",
            "",
            "```text",
            payload,
            "```",
            "",
        ]
    )


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 80)].rstrip() + "\n\n[truncated by harness-codex-preflight]"


def _unsafe_local_distill_reason(text: str) -> str | None:
    for line in text.splitlines():
        normalized = line.strip().lower().lstrip("#*- ")
        if normalized.startswith("status:") or normalized.startswith("**status:**"):
            return "unsafe_operational_status"
        if "live report indicates" in normalized:
            return "unsafe_operational_status"
        if any(center in normalized for center in ("codex", "claude", "antigravity")) and any(
            state in normalized for state in (" ready", " unavailable", " degraded", "blocked", "reset")
        ):
            return "unsafe_operational_status"
    return None
