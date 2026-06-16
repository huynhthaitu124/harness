from __future__ import annotations

import re
from typing import Any


PATH_RE = re.compile(r"(?<![\w/.-])[\w./ -]+\.(?:py|js|jsx|ts|tsx|md|json|html|css|go|rs|java|php|rb|cs|sh|yaml|yml|toml)\b")

FAST_HINTS = (
    "typo",
    "copy",
    "text",
    "label",
    "css",
    "style",
    "rename",
    "format",
    "đổi chữ",
    "sửa chữ",
    "chỉnh text",
)

DEEP_HINTS = (
    "repo-wide",
    "whole repo",
    "codebase",
    "architecture",
    "kiến trúc",
    "refactor",
    "debug",
    "research",
    "nghiên cứu",
    "multi-agent",
    "handoff",
    "token",
    "rag",
    "memory",
    "center",
    "security",
)


def classify_harness_mode(task: str) -> dict[str, Any]:
    """Decide whether Harness should stay out of the way or prepare context."""
    lowered = task.lower()
    explicit_paths = [match.group(0).strip() for match in PATH_RE.finditer(task)]
    if explicit_paths and not any(hint in lowered for hint in DEEP_HINTS):
        return {
            "mode": "fast",
            "harness_required": False,
            "reason": "explicit file path supplied and task is not broad",
            "next_step": "edit_directly_after_reading_the_named_file",
            "explicit_paths": explicit_paths,
        }
    if any(hint in lowered for hint in DEEP_HINTS):
        return {
            "mode": "deep",
            "harness_required": True,
            "reason": "task is broad, ambiguous, or likely to spend repo context",
            "next_step": "use_harness_locate_context_then_read_real_files_before_editing",
            "explicit_paths": explicit_paths,
        }
    if any(hint in lowered for hint in FAST_HINTS) and len(task.split()) <= 18:
        return {
            "mode": "fast",
            "harness_required": False,
            "reason": "small explicit edit hint",
            "next_step": "proceed_directly_if_the_target_is_clear",
            "explicit_paths": explicit_paths,
        }
    return {
        "mode": "light",
        "harness_required": False,
        "reason": "default to light navigation without forcing full RAG",
        "next_step": "use_harness_locate_context_if_target_files_are_unclear",
        "explicit_paths": explicit_paths,
    }
