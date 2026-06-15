from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from harness_core.context_budget import iter_text_files

TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def build_index(root: Path, index_path: Path) -> dict[str, Any]:
    docs = []
    document_frequency: dict[str, int] = {}
    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        terms = _terms(f"{rel}\n{text}")
        counts: dict[str, int] = {}
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
        for term in counts:
            document_frequency[term] = document_frequency.get(term, 0) + 1
        docs.append({"path": rel, "terms": counts, "length": len(terms)})
    index = {"version": 1, "root": str(root), "documents": docs, "document_frequency": document_frequency}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def search_index(index_path: Path, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    query_terms = _terms(query)
    doc_count = max(1, len(index["documents"]))
    results = []
    for doc in index["documents"]:
        score = 0.0
        for term in query_terms:
            tf = doc["terms"].get(term, 0)
            if not tf:
                continue
            df = index["document_frequency"].get(term, 1)
            idf = math.log((doc_count + 1) / df)
            score += (1 + math.log(tf)) * idf
        if score:
            results.append({"path": doc["path"], "score": round(score, 4)})
    return sorted(results, key=lambda item: (-item["score"], item["path"]))[:top_k]


def build_indexed_context_pack(
    root: Path,
    index_path: Path,
    query: str,
    top_k: int = 5,
    max_chars_per_file: int = 1200,
) -> str:
    results = search_index(index_path, query, top_k=top_k)
    sections = [f"# Indexed context pack\nquery: {query}\nroot: {root}\n"]
    for result in results:
        rel = result["path"]
        path = root / rel
        text = path.read_text(encoding="utf-8", errors="ignore")
        sections.append(f"\n## {rel}\nscore: {result['score']}\n```text\n{text[:max_chars_per_file]}\n```\n")
    return "\n".join(sections)


def _terms(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
