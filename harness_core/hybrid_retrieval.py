from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from harness_core.context_budget import iter_text_files
TERM_RE = re.compile(r"[A-Za-z0-9]+")
SYMBOL_RE = re.compile(r"^\s*(def|class|async def|function|const|let|var)\s+.+")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+.+")


def retrieve_hybrid_chunks(
    root: Path,
    query: str,
    *,
    top_k: int = 5,
    chunk_lines: int = 40,
    overlap_lines: int = 8,
) -> list[dict[str, Any]]:
    candidates = _build_candidates(root, chunk_lines=chunk_lines, overlap_lines=overlap_lines)
    query_terms = _tokens(query)
    if not query_terms or not candidates:
        return []

    document_frequency: Counter[str] = Counter()
    for candidate in candidates:
        document_frequency.update(set(candidate["terms"]))
    average_length = sum(len(candidate["terms"]) for candidate in candidates) / len(candidates)

    for candidate in candidates:
        bm25 = _bm25_score(
            candidate["terms"],
            query_terms,
            document_frequency,
            len(candidates),
            average_length,
        )
        path_symbol_terms = set(_tokens(f"{candidate['path']} {candidate['symbol']}"))
        boost_matches = sum(1 for term in set(query_terms) if term in path_symbol_terms)
        path_symbol_boost = boost_matches * 1.5
        candidate["bm25_score"] = round(bm25, 4)
        candidate["path_symbol_boost"] = round(path_symbol_boost, 4)
        candidate["score"] = round(bm25 + path_symbol_boost, 4)

    ranked = sorted(candidates, key=lambda item: (-item["score"], item["path"], item["start_line"]))
    relevant = [candidate for candidate in ranked if candidate["score"] > 0]
    return _select_diverse(relevant, top_k)


def build_hybrid_context_pack(
    root: Path,
    query: str,
    *,
    top_k: int = 5,
    chunk_lines: int = 40,
    overlap_lines: int = 8,
) -> str:
    chunks = retrieve_hybrid_chunks(
        root,
        query,
        top_k=top_k,
        chunk_lines=chunk_lines,
        overlap_lines=overlap_lines,
    )
    sections = [f"# Hybrid context pack\nquery: {query}\nroot: {root}\n"]
    for chunk in chunks:
        sections.append(
            "\n".join(
                [
                    f"## {chunk['path']}",
                    f"lines: {chunk['start_line']}-{chunk['end_line']}",
                    f"symbol: {chunk['symbol']}",
                    f"score: {chunk['score']}",
                    f"bm25_score: {chunk['bm25_score']}",
                    f"path_symbol_boost: {chunk['path_symbol_boost']}",
                    "```text",
                    chunk["text"],
                    "```",
                    "",
                ]
            )
        )
    return "\n".join(sections)


def _build_candidates(root: Path, *, chunk_lines: int, overlap_lines: int) -> list[dict[str, Any]]:
    if chunk_lines <= 0:
        raise ValueError("chunk_lines must be positive")
    step = max(1, chunk_lines - max(0, overlap_lines))
    candidates: list[dict[str, Any]] = []
    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for start in range(0, len(lines), step):
            chunk = lines[start : start + chunk_lines]
            if not chunk:
                continue
            text = "\n".join(chunk)
            symbol = _symbol_at_or_before(lines, start)
            candidates.append(
                {
                    "path": rel,
                    "start_line": start + 1,
                    "end_line": start + len(chunk),
                    "symbol": symbol,
                    "text": text,
                    "terms": _tokens(text),
                }
            )
            if start + chunk_lines >= len(lines):
                break
    return candidates


def _bm25_score(
    terms: list[str],
    query_terms: list[str],
    document_frequency: Counter[str],
    document_count: int,
    average_length: float,
) -> float:
    counts = Counter(terms)
    length = max(1, len(terms))
    score = 0.0
    k1 = 1.5
    b = 0.75
    for term in set(query_terms):
        frequency = counts.get(term, 0)
        if frequency == 0:
            continue
        df = document_frequency.get(term, 0)
        idf = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
        denominator = frequency + k1 * (1 - b + b * length / max(1.0, average_length))
        score += idf * ((frequency * (k1 + 1)) / denominator)
    return score


def _select_diverse(candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for candidate in candidates:
        if candidate["path"] in seen_paths:
            continue
        selected.append(candidate)
        seen_paths.add(candidate["path"])
        if len(selected) >= top_k:
            return selected
    for candidate in candidates:
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) >= top_k:
            break
    return selected


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TERM_RE.finditer(text)]


def _symbol_at_or_before(lines: list[str], start: int) -> str:
    for index in range(min(start, len(lines) - 1), -1, -1):
        line = lines[index].strip()
        if SYMBOL_RE.match(line) or HEADING_RE.match(line):
            return line
    return "(file top)"
