from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_core.command_policy import validate_command

CENTER_ORDER = ["claude", "codex", "antigravity"]

DEFAULT_PROMPT = (
    "Summarize this harness architecture in no more than 250 words. "
    "Cite exactly five repository paths and identify exactly three operational risks."
)
DEFAULT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5},
        "risks": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
    },
    "required": ["summary", "citations", "risks"],
}


def init_experiment_queue(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    fingerprint_payload = json.dumps(
        {"prompt": DEFAULT_PROMPT, "output_schema": DEFAULT_SCHEMA}, sort_keys=True, separators=(",", ":")
    )
    payload = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "center_order": CENTER_ORDER,
        "tasks": [
            {
                "id": "harness-architecture-summary-v1",
                "task_fingerprint": hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
                "prompt": DEFAULT_PROMPT,
                "output_schema": DEFAULT_SCHEMA,
                "quality_rules": ["summary_word_count<=250", "citation_count=5", "risk_count=3"],
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def plan_next_experiment(queue_path: Path, experiments_path: Path, readiness: dict[str, Any]) -> dict[str, Any]:
    queue = init_experiment_queue(queue_path)
    ready = set(readiness.get("ready_centers", []))
    if not ready:
        return {
            "verdict": "BLOCKED",
            "reason": "no_ready_cloud_center",
            "reset_hints": _reset_hints(readiness),
        }

    runs = _load_runs(experiments_path)
    for task in queue.get("tasks", []):
        for center in queue.get("center_order", CENTER_ORDER):
            if center not in ready:
                continue
            experiment_id = f"{task['id']}:{center}"
            recorded = {
                run.get("variant")
                for run in runs
                if run.get("experiment_id") == experiment_id and run.get("center") == center
            }
            for variant in ("baseline", "harness"):
                if variant not in recorded:
                    return {
                        "verdict": "READY",
                        "run": {
                            "experiment_id": experiment_id,
                            "task_id": task["id"],
                            "task_fingerprint": task["task_fingerprint"],
                            "center": center,
                            "variant": variant,
                            "context_mode": "raw_repo" if variant == "baseline" else "compact_harness",
                            "usage_ingestion": _usage_ingestion(center),
                            "prompt": task["prompt"],
                            "output_schema": task["output_schema"],
                            "quality_rules": task["quality_rules"],
                        },
                    }
    return {"verdict": "COMPLETE", "reason": "all_ready_center_runs_recorded"}


def build_experiment_blueprint(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    center = run["center"]
    slug = _safe_slug(f"{run['experiment_id']}:{run['variant']}")
    artifact_dir = root / "production_artifacts" / "experiments" / slug
    prompt_path = artifact_dir / "prompt.txt"
    schema_path = artifact_dir / "schema.json"
    raw_output_path = artifact_dir / ("raw-output.jsonl" if center == "codex" else "raw-output.json")
    quality_report_path = artifact_dir / "quality-report.json"
    prompt = _render_prompt(run)
    if center == "claude":
        command = ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json", "--json-schema", str(schema_path)]
        usage_ingestion = "claude_json"
        measurement_mode = "token_usage"
    elif center == "codex":
        command = ["codex", "exec", "--json", prompt]
        usage_ingestion = "codex_jsonl"
        measurement_mode = "token_usage"
    elif center == "antigravity":
        command = ["agy", "--print", prompt]
        usage_ingestion = "manual"
        measurement_mode = "quality_only"
    else:
        raise ValueError(f"unknown center: {center}")
    return {
        "execute": False,
        "center": center,
        "variant": run["variant"],
        "experiment_id": run["experiment_id"],
        "task_fingerprint": run.get("task_fingerprint"),
        "context_mode": run.get("context_mode"),
        "usage_ingestion": usage_ingestion,
        "measurement_mode": measurement_mode,
        "artifact_dir": str(artifact_dir),
        "prompt_path": str(prompt_path),
        "schema_path": str(schema_path),
        "raw_output_path": str(raw_output_path),
        "quality_report_path": str(quality_report_path),
        "command": command,
        "next_steps": [
            "write prompt_path and schema_path",
            "execute command only if readiness still reports this center ready",
            "score output with harness-experiment-quality",
            "ingest measured usage into production_artifacts/experiments.jsonl",
        ],
    }


def prepare_experiment_run(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    blueprint = build_experiment_blueprint(root, run)
    artifact_dir = Path(blueprint["artifact_dir"])
    prompt_path = Path(blueprint["prompt_path"])
    schema_path = Path(blueprint["schema_path"])
    manifest_path = artifact_dir / "manifest.json"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(_render_prompt(run) + "\n", encoding="utf-8")
    schema_path.write_text(json.dumps(run.get("output_schema", {}), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    command_policy = validate_command(" ".join(blueprint["command"]), actor="autopilot")
    manifest = {
        **blueprint,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "quality_rules": run.get("quality_rules", []),
        "command_policy": command_policy,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def _load_runs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    runs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return runs


def _reset_hints(readiness: dict[str, Any]) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    for center, state in readiness.get("centers", {}).items():
        if not isinstance(state, dict):
            continue
        hint = state.get("reset_hint")
        if not hint and isinstance(state.get("quota"), dict):
            hint = state["quota"].get("reset_hint")
        if hint:
            hints[center] = hint
    return hints


def _usage_ingestion(center: str) -> str:
    if center == "claude":
        return "claude_json"
    if center == "codex":
        return "codex_jsonl"
    return "manual"


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")[:120]


def _render_prompt(run: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            run.get("prompt", ""),
            f"Experiment ID: {run.get('experiment_id')}",
            f"Variant: {run.get('variant')}",
            f"Context mode: {run.get('context_mode')}",
            "Return only JSON matching the provided schema.",
        ]
    ).strip()
