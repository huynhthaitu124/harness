from __future__ import annotations

import re
from typing import Any

DENY_PATTERNS = {
    "recursive_delete": re.compile(r"(^|[;&|]\s*)rm\s+[^\n]*(?:-rf|-fr|--recursive)", re.IGNORECASE),
    "git_hard_reset": re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    "git_checkout_overwrite": re.compile(r"\bgit\s+checkout\s+--\s+", re.IGNORECASE),
    "privilege_escalation": re.compile(r"(^|[;&|]\s*)sudo\s+", re.IGNORECASE),
    "download_to_shell": re.compile(r"\b(?:curl|wget)\b[^|]*\|\s*(?:sh|bash|zsh)\b", re.IGNORECASE),
}
REVIEW_PATTERNS = {
    "package_install": re.compile(r"\b(?:brew|npm|pnpm|yarn|pip|pip3|cargo)\s+(?:install|add)\b", re.IGNORECASE),
    "model_download": re.compile(r"\bollama\s+pull\b", re.IGNORECASE),
    "git_publish": re.compile(r"\bgit\s+(?:push|commit|tag)\b", re.IGNORECASE),
    "remote_write": re.compile(r"\b(?:curl|wget)\b[^\n]*(?:-X\s*(?:POST|PUT|PATCH|DELETE)|--data|-d\s)", re.IGNORECASE),
}
ALLOW_PATTERNS = [
    re.compile(r"^python3?\s+-m\s+(?:unittest|pytest)\b"),
    re.compile(r"^(?:rg|sed|cat|head|tail|find|wc|ls)\b"),
    re.compile(r"^scripts/harness-(?:doctor|readiness|benchmark|route|autopilot|campaign|retrieval-eval|research|memory)\b"),
    re.compile(r"^(?:sysctl|memory_pressure|df|vm_stat)\b"),
    re.compile(r"^ollama\s+(?:ps|list|show)\b"),
]


def validate_command(command: str, *, actor: str = "human") -> dict[str, Any]:
    stripped = command.strip()
    deny_reasons = [name for name, pattern in DENY_PATTERNS.items() if pattern.search(stripped)]
    if deny_reasons:
        return _result("DENY", actor, stripped, deny_reasons)
    review_reasons = [name for name, pattern in REVIEW_PATTERNS.items() if pattern.search(stripped)]
    if review_reasons:
        return _result("REVIEW", actor, stripped, review_reasons)
    if any(pattern.search(stripped) for pattern in ALLOW_PATTERNS):
        return _result("ALLOW", actor, stripped, ["known_read_or_validation_command"])
    return _result("REVIEW", actor, stripped, ["unknown_command_shape"])


def _result(verdict: str, actor: str, command: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "actor": actor,
        "command": command,
        "reasons": reasons,
        "autonomous_execution_allowed": verdict == "ALLOW" and actor == "autopilot",
    }
