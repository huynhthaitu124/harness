from __future__ import annotations

from pathlib import Path

TEXT_EXTENSIONS = {
    ".cs",
    ".css",
    ".go",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".rs",
    ".sql",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    ".harness",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "production_artifacts",
}


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)
    return sorted(files)


def build_context_pack(root: Path, query: str, max_files: int = 12, max_chars_per_file: int = 1200) -> str:
    terms = [term.lower() for term in query.split() if len(term) > 2]
    scored: list[tuple[int, Path]] = []
    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix().lower()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        haystack = f"{rel}\n{text[:20000].lower()}"
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, path))

    selected = [path for _, path in sorted(scored, key=lambda item: (-item[0], item[1]))[:max_files]]
    if not selected:
        selected = iter_text_files(root)[: max_files // 2 or 1]

    sections = [f"# Context pack\nquery: {query}\nroot: {root}\n"]
    for path in selected:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        snippet = _best_snippet(text, terms, max_chars_per_file)
        sections.append(f"\n## {rel}\n```text\n{snippet}\n```\n")
    return "\n".join(sections)


def measure_context_savings(root: Path, compact_context: str) -> dict[str, float | int]:
    raw_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in iter_text_files(root))
    raw_tokens = estimate_tokens(raw_text)
    compact_tokens = estimate_tokens(compact_context)
    savings = 0.0 if raw_tokens == 0 else max(0.0, (raw_tokens - compact_tokens) / raw_tokens * 100)
    return {
        "raw_tokens": raw_tokens,
        "compact_tokens": compact_tokens,
        "savings_percent": round(savings, 2),
    }


def _best_snippet(text: str, terms: list[str], max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    lower = text.lower()
    hits = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not hits:
        return text[:max_chars]
    center = min(hits)
    start = max(0, center - max_chars // 3)
    end = min(len(text), start + max_chars)
    return text[start:end]
