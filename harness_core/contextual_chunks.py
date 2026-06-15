from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harness_core.context_budget import iter_text_files
from harness_core.search_index import _terms

SYMBOL_RE = re.compile(r"^\s*(def|class|async def|function|const|let|var)\s+.+")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+.+")


def build_contextual_chunks(
    root: Path,
    query: str,
    *,
    top_k: int | None = None,
    max_chars_per_chunk: int = 1200,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        score = _score_text(rel, text, query)
        if score <= 0:
            continue
        snippet, line_index = _relevant_snippet(text, query, max_chars_per_chunk)
        symbol = _nearest_symbol(text.splitlines(), line_index)
        context = _context_header(rel, query, symbol, score)
        chunks.append(
            {
                "path": rel,
                "score": round(score, 4),
                "symbol": symbol,
                "context": context,
                "text": snippet,
            }
        )
    chunks.sort(key=lambda chunk: (-chunk["score"], chunk["path"]))
    if top_k is not None:
        return chunks[:top_k]
    return chunks


def build_contextual_context_pack(
    root: Path,
    query: str,
    *,
    top_k: int = 5,
    max_chars_per_chunk: int = 1200,
) -> str:
    chunks = build_contextual_chunks(root, query, top_k=top_k, max_chars_per_chunk=max_chars_per_chunk)
    sections = [f"# Contextual context pack\nquery: {query}\nroot: {root}\n"]
    for chunk in chunks:
        sections.append(
            "\n".join(
                [
                    f"## {chunk['path']}",
                    f"score: {chunk['score']}",
                    f"symbol: {chunk['symbol']}",
                    "```text",
                    chunk["context"],
                    "",
                    chunk["text"],
                    "```",
                    "",
                ]
            )
        )
    return "\n".join(sections)


def _score_text(path: str, text: str, query: str) -> float:
    query_terms = set(_terms(query))
    if not query_terms:
        return 0.0
    doc_terms = _terms(f"{path}\n{text}")
    score = 0.0
    for term in query_terms:
        score += doc_terms.count(term)
    return score


def _relevant_snippet(text: str, query: str, max_chars: int) -> tuple[str, int]:
    lines = text.splitlines()
    query_terms = set(_terms(query))
    best_index = 0
    best_score = -1
    for index, line in enumerate(lines):
        terms = _terms(line)
        score = sum(1 for term in terms if term in query_terms)
        if score > best_score:
            best_index = index
            best_score = score
    snippet_lines: list[str] = []
    total = 0
    start = max(0, best_index - 4)
    for line in lines[start:]:
        next_total = total + len(line) + 1
        if snippet_lines and next_total > max_chars:
            break
        snippet_lines.append(line)
        total = next_total
    return "\n".join(snippet_lines)[:max_chars], best_index


def _nearest_symbol(lines: list[str], line_index: int) -> str:
    for index in range(min(line_index, len(lines) - 1), -1, -1):
        line = lines[index].strip()
        if SYMBOL_RE.match(line) or HEADING_RE.match(line):
            return line
    for line in lines:
        stripped = line.strip()
        if SYMBOL_RE.match(stripped) or HEADING_RE.match(stripped):
            return stripped
    return "(file top)"


def _context_header(path: str, query: str, symbol: str, score: float) -> str:
    return "\n".join(
        [
            f"path: {path}",
            f"query: {query}",
            f"symbol: {symbol}",
            f"local_relevance_score: {round(score, 4)}",
        ]
    )
