from __future__ import annotations

from typing import Any


EMBEDDING_MODEL_PRIORITY = ("qwen3-embedding", "embeddinggemma", "all-minilm")


def choose_embedding_model(
    installed_models: list[str],
    *,
    requested_model: str | None = None,
    priority: tuple[str, ...] = EMBEDDING_MODEL_PRIORITY,
) -> dict[str, Any]:
    """Pick the best Ollama embedding model without confusing it with chat models."""
    installed = list(installed_models)
    if requested_model and requested_model != "auto":
        return {
            "model": requested_model,
            "installed": _model_installed(requested_model, installed),
            "source": "requested",
            "priority": list(priority),
        }

    for model in priority:
        if _model_installed(model, installed):
            return {
                "model": model,
                "installed": True,
                "source": "installed_priority",
                "priority": list(priority),
            }

    return {
        "model": priority[0],
        "installed": False,
        "source": "default_priority",
        "priority": list(priority),
    }


def _model_installed(model: str, installed_models: list[str]) -> bool:
    return any(name == model or name.startswith(f"{model}:") for name in installed_models)
