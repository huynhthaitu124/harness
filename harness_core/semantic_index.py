from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from harness_core.context_budget import iter_text_files
from harness_core.local_model_gate import local_model_decision

Embedder = Callable[[list[str]], list[list[float]]]


def build_semantic_index(
    root: Path,
    index_path: Path,
    *,
    embedder: Embedder,
    model: str,
    chunk_lines: int = 40,
    overlap_lines: int = 8,
) -> dict[str, Any]:
    existing = _load_existing(index_path, model)
    cached = {(item["key"], item["content_hash"]): item["vector"] for item in existing.get("chunks", [])}
    chunks = _chunk_repository(root, chunk_lines=chunk_lines, overlap_lines=overlap_lines)
    missing = [chunk for chunk in chunks if (chunk["key"], chunk["content_hash"]) not in cached]
    vectors = embedder([chunk["text"] for chunk in missing]) if missing else []
    if len(vectors) != len(missing):
        raise ValueError("embedder returned a different vector count than requested")
    generated = {chunk["key"]: vector for chunk, vector in zip(missing, vectors)}

    records = []
    reused_count = 0
    for chunk in chunks:
        cache_key = (chunk["key"], chunk["content_hash"])
        if cache_key in cached:
            vector = cached[cache_key]
            reused_count += 1
        else:
            vector = generated[chunk["key"]]
        records.append({**chunk, "vector": vector})

    payload = {"version": 1, "root": str(root), "model": model, "chunks": records}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {
        "index_path": str(index_path),
        "model": model,
        "chunk_count": len(records),
        "embedded_count": len(missing),
        "reused_count": reused_count,
    }


def search_semantic_index(
    index_path: Path,
    query: str,
    *,
    embedder: Embedder,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    query_vectors = embedder([query])
    if len(query_vectors) != 1:
        raise ValueError("embedder must return one query vector")
    query_vector = query_vectors[0]
    results = []
    for chunk in index["chunks"]:
        score = _cosine_similarity(query_vector, chunk["vector"])
        results.append(
            {
                "path": chunk["path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "score": round(score, 6),
                "text": chunk["text"],
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["path"], item["start_line"]))[:top_k]


def plan_semantic_index(
    *,
    machine: dict[str, Any],
    installed_models: list[str],
    model: str = "embeddinggemma",
) -> dict[str, Any]:
    gate = local_model_decision(machine, "light")
    if not gate["allow"]:
        return {
            "mode": "hybrid_lexical",
            "use_ollama": False,
            "model": model,
            "reasons": gate["reasons"],
            "fallback": "Use harness_hybrid_context_pack until live memory and swap improve.",
        }
    installed = any(name == model or name.startswith(f"{model}:") for name in installed_models)
    if not installed:
        return {
            "mode": "ollama_embedding_setup",
            "use_ollama": False,
            "model": model,
            "needs_model": True,
            "pull_command": f"ollama pull {model}",
            "reasons": gate["reasons"],
        }
    return {
        "mode": "ollama_semantic_index",
        "use_ollama": True,
        "model": model,
        "max_context_tokens": gate["max_context_tokens"],
        "reasons": gate["reasons"],
    }


def ollama_embed(texts: list[str], *, model: str = "embeddinggemma", host: str = "http://localhost:11434") -> list[list[float]]:
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = Request(f"{host.rstrip('/')}/api/embed", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["embeddings"]


def _chunk_repository(root: Path, *, chunk_lines: int, overlap_lines: int) -> list[dict[str, Any]]:
    step = max(1, chunk_lines - max(0, overlap_lines))
    chunks: list[dict[str, Any]] = []
    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for start in range(0, len(lines), step):
            selected = lines[start : start + chunk_lines]
            if not selected:
                continue
            text = "\n".join(selected)
            key = f"{rel}:{start + 1}:{start + len(selected)}"
            chunks.append(
                {
                    "key": key,
                    "path": rel,
                    "start_line": start + 1,
                    "end_line": start + len(selected),
                    "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "text": text,
                }
            )
            if start + chunk_lines >= len(lines):
                break
    return chunks


def _load_existing(index_path: Path, model: str) -> dict[str, Any]:
    if not index_path.exists():
        return {"chunks": []}
    existing = json.loads(index_path.read_text(encoding="utf-8"))
    if existing.get("model") != model:
        return {"chunks": []}
    return existing


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
