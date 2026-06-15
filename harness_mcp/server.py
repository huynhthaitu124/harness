from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_core.capability_scaffold import scaffold_capability
from harness_core.capability_registry import evaluate_capability, list_capabilities, promote_capability
from harness_core.agent_rag import build_agent_rag_pack
from harness_core.autopilot import plan_next_growth_action
from harness_core.context_budget import build_context_pack, measure_context_savings
from harness_core.context_pack_audit import audit_context_packs
from harness_core.contextual_chunks import build_contextual_context_pack
from harness_core.command_policy import validate_command
from harness_core.codex_preflight import build_codex_preflight
from harness_core.evaluator import evaluate_evidence
from harness_core.experiment_scheduler import (
    build_experiment_blueprint,
    init_experiment_queue,
    plan_next_experiment,
    prepare_experiment_run,
)
from harness_core.experiment_quality import evaluate_experiment_output
from harness_core.feature_state import complete_feature, init_feature_list, next_feature
from harness_core.growth_runner import run_evaluated_growth_cycle
from harness_core.growth_campaign import campaign_status, init_campaign
from harness_core.harness_doctor import run_harness_doctor
from harness_core.health_suite import aggregate_health
from harness_core.hybrid_retrieval import build_hybrid_context_pack
from harness_core.local_model_gate import local_model_decision
from harness_core.local_worker import plan_local_worker
from harness_core.local_rag_pipeline import plan_local_rag_pipeline
from harness_core.memory_auditor import audit_handoffs
from harness_core.memory_index import build_memory_pack, record_memory, search_memories, sync_artifact_memories
from harness_core.mcp_conformance import run_mcp_conformance
from harness_core.mcp_security import audit_mcp_security
from harness_core.output_compactor import compact_tool_output
from harness_core.project_analyzer import generate_grill_questions, write_grill_answers_to_harness_md
from harness_core.project_init import analyze_project, init_project_full, init_project_harness
from harness_core.quota_feedback import apply_worker_feedback
from harness_core.readiness import build_readiness_report
from harness_core.research_registry import (
    due_research_sources,
    init_research_registry,
    record_source_check,
    refresh_research_sources,
)
from harness_core.retrieval_eval import evaluate_hybrid_dataset
from harness_core.router import choose_center, default_state, load_state, save_state, suggest_model_tier
from harness_core.trajectory import begin_trajectory, record_step, end_trajectory, list_trajectories, classify_failure
from harness_core.telemetry import new_chain, begin_span, end_span, summarize_chain, recent_telemetry
from harness_core.lifecycle import fire_event, list_hooks, register_hook
from harness_core.project_growth import (
    growth_status, next_project_action, record_routing_evidence,
    extract_pattern_from_trajectory, search_patterns,
)
from harness_core.hack_detector import check_trajectory, scan_trajectories
from harness_core.search_index import build_index, build_indexed_context_pack, search_index
from harness_core.semantic_index import plan_semantic_index
from harness_core.self_growth import run_growth_cycle
from harness_core.structured_worker import plan_structured_local_worker
from harness_core.structured_handoff import validate_structured_handoff, write_structured_handoff
from harness_core.token_experiment import ingest_claude_result, ingest_codex_jsonl, record_experiment_run, summarize_experiments
from harness_core.token_ledger import record_usage, summarize_usage

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path(os.environ.get("HARNESS_STATE_PATH", ROOT / ".harness" / "state.json"))
ARTIFACTS_DIR = Path(os.environ.get("HARNESS_ARTIFACTS_DIR", ROOT / ".harness"))
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2024-11-05")


TOOLS = [
    {
        "name": "harness_get_status",
        "description": "Read the current shared harness center, quotas, and routing policy.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "harness_set_center",
        "description": "Set the preferred center to auto, codex, claude, or antigravity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "center": {"type": "string", "enum": ["auto", "codex", "claude", "antigravity"]},
            },
            "required": ["center"],
        },
    },
    {
        "name": "harness_route_task",
        "description": "Decide which center should lead a task and whether RAG/local summarization should run before cloud work. Also returns suggested_model_tier (opus/sonnet/haiku) based on task complexity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "root": {"type": "string", "description": "Project root for project-specific state (optional)"},
            },
            "required": ["task"],
        },
    },
    # ── Phase 1: Tiered model ─────────────────────────────────────────────────
    {
        "name": "harness_suggest_model_tier",
        "description": "Return the suggested Claude model tier (opus/sonnet/haiku) for a task based on complexity keywords. Use this before cloud calls to pick the right model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "root": {"type": "string", "description": "Project root to read per-project model_tiers config (optional)"},
            },
            "required": ["task"],
        },
    },
    # ── Phase 2: Trajectory ──────────────────────────────────────────────────
    {
        "name": "harness_begin_trajectory",
        "description": "Start a new trajectory session to track agent tool calls step-by-step. Returns session_id to pass to harness_record_step and harness_end_trajectory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":    {"type": "string"},
                "center":  {"type": "string"},
                "model":   {"type": "string"},
                "task":    {"type": "string"},
            },
            "required": ["root", "center", "model", "task"],
        },
    },
    {
        "name": "harness_record_step",
        "description": "Record one tool-call step into an active trajectory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":           {"type": "string"},
                "session_id":     {"type": "string"},
                "tool":           {"type": "string"},
                "result_status":  {"type": "string", "description": "ok | tool_error | env_error | timeout"},
                "args_hash":      {"type": "string"},
                "duration_ms":    {"type": "integer"},
                "tokens":         {"type": "integer"},
                "note":           {"type": "string"},
            },
            "required": ["root", "session_id", "tool", "result_status"],
        },
    },
    {
        "name": "harness_end_trajectory",
        "description": "Close a trajectory session and record outcome. Automatically extracts patterns on success and classifies failure category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":         {"type": "string"},
                "session_id":   {"type": "string"},
                "outcome":      {"type": "string", "description": "success | failure | partial"},
                "failure_step": {"type": "integer"},
            },
            "required": ["root", "session_id", "outcome"],
        },
    },
    {
        "name": "harness_list_trajectories",
        "description": "List recent trajectory sessions with outcome and failure category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":  {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["root"],
        },
    },
    # ── Phase 3: Lifecycle hooks ──────────────────────────────────────────────
    {
        "name": "harness_fire_event",
        "description": "Fire a lifecycle event (before_tool / after_tool / on_error / on_decision). Triggers all matching hooks including webhooks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":          {"type": "string"},
                "event":         {"type": "string", "description": "before_tool | after_tool | on_error | on_decision | on_session_start | on_session_end"},
                "tool":          {"type": "string"},
                "session_id":    {"type": "string"},
                "center":        {"type": "string"},
                "result_status": {"type": "string"},
                "duration_ms":   {"type": "integer"},
                "tokens":        {"type": "integer"},
                "error":         {"type": "string"},
            },
            "required": ["root", "event", "tool"],
        },
    },
    {
        "name": "harness_register_hook",
        "description": "Register a lifecycle hook for a project. Hooks run on every matching tool call event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":         {"type": "string"},
                "event":        {"type": "string", "description": "before_tool | after_tool | on_error | on_decision | on_session_start | on_session_end"},
                "tool_pattern": {"type": "string", "description": "Tool name or glob pattern (e.g. shell_* or *)"},
                "action":       {"type": "string", "description": "allow | cancel | webhook | record | require_confirm | record_trajectory_failure"},
                "webhook_url":  {"type": "string"},
                "enabled":      {"type": "boolean", "default": True},
            },
            "required": ["root", "event", "action"],
        },
    },
    {
        "name": "harness_list_hooks",
        "description": "List all lifecycle hooks configured for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    # ── Phase 4: Per-project growth ───────────────────────────────────────────
    {
        "name": "harness_project_growth_status",
        "description": "Show the self-growth state of a specific project: feature progress, pattern count, routing evidence, experiment queue.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_next_project_action",
        "description": "Return the highest-priority growth action for a specific project (run experiment, implement feature, collect evidence, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_record_routing_evidence",
        "description": "Record the outcome of a routing decision for a project, enabling the harness to learn which centers/models work best over time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":        {"type": "string"},
                "center":      {"type": "string"},
                "task_type":   {"type": "string"},
                "outcome":     {"type": "string", "description": "success | failure | partial"},
                "model_tier":  {"type": "string"},
                "duration_ms": {"type": "integer"},
            },
            "required": ["root", "center", "task_type", "outcome"],
        },
    },
    {
        "name": "harness_search_patterns",
        "description": "Search the per-project pattern database for successful solution patterns matching a query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":  {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["root", "query"],
        },
    },
    # ── Phase 5: Telemetry ────────────────────────────────────────────────────
    {
        "name": "harness_new_chain",
        "description": "Start a new telemetry chain (top-level query). Returns chain_id for span tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":   {"type": "string"},
                "task":   {"type": "string"},
                "center": {"type": "string"},
            },
            "required": ["root", "task", "center"],
        },
    },
    {
        "name": "harness_begin_span",
        "description": "Start a telemetry span for one tool call within a chain.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":     {"type": "string"},
                "chain_id": {"type": "string"},
                "tool":     {"type": "string"},
                "depth":    {"type": "integer", "default": 0},
            },
            "required": ["root", "chain_id", "tool"],
        },
    },
    {
        "name": "harness_end_span",
        "description": "Close a telemetry span and record timing + token counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":       {"type": "string"},
                "chain_id":   {"type": "string"},
                "span_id":    {"type": "string"},
                "tokens_in":  {"type": "integer", "default": 0},
                "tokens_out": {"type": "integer", "default": 0},
                "status":     {"type": "string", "default": "ok"},
            },
            "required": ["root", "chain_id", "span_id"],
        },
    },
    {
        "name": "harness_chain_summary",
        "description": "Return timing and token summary for a completed chain.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":     {"type": "string"},
                "chain_id": {"type": "string"},
            },
            "required": ["root", "chain_id"],
        },
    },
    {
        "name": "harness_recent_telemetry",
        "description": "Return summaries of the most recent telemetry chains for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":  {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["root"],
        },
    },
    # ── Phase 6: Hack detection ───────────────────────────────────────────────
    {
        "name": "harness_check_trajectory_hacks",
        "description": "Analyse a single trajectory for evaluation gaming signals (artifact unchanged, empty output success, circular tool calls, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":                  {"type": "string"},
                "session_id":            {"type": "string"},
                "prior_artifact_hash":   {"type": "string"},
                "current_artifact_hash": {"type": "string"},
                "prior_score":           {"type": "number"},
                "current_score":         {"type": "number"},
            },
            "required": ["root", "session_id"],
        },
    },
    {
        "name": "harness_scan_hacks",
        "description": "Scan all recent trajectories for hack signals and return a summary with hack rate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":  {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["root"],
        },
    },
    {
        "name": "harness_record_handoff",
        "description": "Persist a compact handoff note for Codex, Claude, and Antigravity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "center": {"type": "string"},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "harness_delegate_claude",
        "description": "Run Claude Code CLI in non-interactive print mode with a compact context pack. Requires Claude Code authentication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "timeout_sec": {"type": "integer", "default": 300},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "harness_delegate_antigravity",
        "description": "Run Antigravity CLI in non-interactive print mode with a compact context pack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "timeout_sec": {"type": "integer", "default": 300},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "harness_benchmark_context",
        "description": "Estimate token savings from compact context packs versus raw text files for a repository or folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "query": {"type": "string"},
                "max_files": {"type": "integer", "default": 12},
            },
            "required": ["root", "query"],
        },
    },
    {
        "name": "harness_init_features",
        "description": "Create a default-fail feature_list.json for long-running harness work.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}}},
            "required": ["path", "features"],
        },
    },
    {
        "name": "harness_next_feature",
        "description": "Read the next pending/default-fail feature from a feature_list.json.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "harness_complete_feature",
        "description": "Mark a feature complete only when evidence is supplied.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "feature_id": {"type": "integer"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["path", "feature_id", "evidence"],
        },
    },
    {
        "name": "harness_evaluate_evidence",
        "description": "Fresh-context style default-fail evaluator for required evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "required": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["root", "required", "evidence"],
        },
    },
    {
        "name": "harness_record_usage",
        "description": "Append a token/cost usage entry to the shared JSONL ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "center": {"type": "string"},
                "input_tokens": {"type": "integer"},
                "output_tokens": {"type": "integer"},
                "cost_usd": {"type": "number"},
                "label": {"type": "string"},
            },
            "required": ["path", "center", "input_tokens", "output_tokens", "cost_usd"],
        },
    },
    {
        "name": "harness_usage_report",
        "description": "Summarize token/cost usage by center from the shared JSONL ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "harness_index_repo",
        "description": "Build a lightweight local inverted index for repository search.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "index_path": {"type": "string"}},
            "required": ["root", "index_path"],
        },
    },
    {
        "name": "harness_search_index",
        "description": "Search a lightweight local repository index before spending cloud tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "index_path": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["index_path", "query"],
        },
    },
    {
        "name": "harness_indexed_context_pack",
        "description": "Build a compact context pack from local index search results before cloud reasoning.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "index_path": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
                "max_chars_per_file": {"type": "integer", "default": 1200}
            },
            "required": ["root", "index_path", "query"],
        },
    },
    {
        "name": "harness_contextual_context_pack",
        "description": "Build a compact context pack whose chunks include path, query, symbol, and relevance context headers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
                "max_chars_per_chunk": {"type": "integer", "default": 1200},
            },
            "required": ["root", "query"],
        },
    },
    {
        "name": "harness_local_context_pack",
        "description": "Use the configured local LLM sub-agent (Ollama) to pre-fetch and summarise context for a query before passing it to a cloud model. Reads local_llm config from .harness/project.json. Falls back to standard contextual context pack if no local LLM is configured.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root":               {"type": "string", "description": "Target project root"},
                "query":              {"type": "string", "description": "Context query"},
                "top_k":              {"type": "integer", "default": 6},
                "max_chars_per_chunk":{"type": "integer", "default": 1200},
                "max_summary_chars":  {"type": "integer", "default": 3000},
            },
            "required": ["root", "query"],
        },
    },
    {
        "name": "harness_init_project",
        "description": "Initialize an Anthropic-style filesystem harness in a project: init.sh, feature_list.json, and artifacts folders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "features": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["root", "features"],
        },
    },
    {
        "name": "harness_analyze_project",
        "description": "Analyze a target project to detect language, framework, routing keywords, initial features, and seed memories. Returns analysis JSON for use with harness_init_full.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
            },
            "required": ["root"],
        },
    },
    {
        "name": "harness_init_full",
        "description": "Full project-agnostic harness init: configure .harness/state.json, build BM25 index, seed memory, write HARNESS.md and configs/claude-mcp.json. Pass analysis from harness_analyze_project or agent-enriched JSON.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "harness_root": {"type": "string"},
                "analysis": {"type": "object"},
                "dry_run": {"type": "boolean"},
                "skip_index": {"type": "boolean"},
            },
            "required": ["root", "harness_root", "analysis"],
        },
    },
    {
        "name": "harness_grill_project",
        "description": "Return the grill questions for a project, or write pre-collected answers into HARNESS.md [CUSTOMIZE] section. Pass answers as a dict to populate; omit to just get the question list.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "answers": {"type": "object"},
            },
            "required": ["root"],
        },
    },
    {
        "name": "harness_local_model_gate",
        "description": "Decide whether local model workers should run given live machine state and task complexity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "machine": {"type": "object"},
                "task_complexity": {"type": "string"},
            },
            "required": ["machine", "task_complexity"],
        },
    },
    {
        "name": "harness_plan_local_worker",
        "description": "Plan whether a local model worker can handle a task or should fall back to deterministic extractive RAG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "machine": {"type": "object"},
                "task_complexity": {"type": "string"},
                "model": {"type": "string", "default": "qwen35-codex-local"}
            },
            "required": ["task", "machine", "task_complexity"],
        },
    },
    {
        "name": "harness_plan_structured_local_worker",
        "description": "Plan a gated Ollama structured-output worker call with JSON schema, or fall back to extractive RAG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "machine": {"type": "object"},
                "task_complexity": {"type": "string"},
                "schema": {"type": "object"},
                "model": {"type": "string", "default": "qwen35-codex-local"},
            },
            "required": ["task", "machine", "task_complexity", "schema"],
        },
    },
    {
        "name": "harness_scaffold_capability",
        "description": "Create a draft capability with a skill and tool specification for future harness growth.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["root", "name", "description"],
        },
    },
    {
        "name": "harness_list_capabilities",
        "description": "List scaffolded harness capabilities and their skill/tool spec locations.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_run_growth_cycle",
        "description": "Record a self-growth cycle with sources and proposed actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "topic": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "object"}},
                "actions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["root", "topic", "sources", "actions"],
        },
    },
    {
        "name": "harness_run_evaluated_growth_cycle",
        "description": "Record a self-growth cycle, append usage to the token ledger, and evaluate required evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "topic": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "object"}},
                "actions": {"type": "array", "items": {"type": "string"}},
                "usage": {"type": "object"},
                "required_evidence": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["root", "topic", "sources", "actions", "usage", "required_evidence"],
        },
    },
    {
        "name": "harness_audit_handoffs",
        "description": "Audit handoff files for missing evidence markers and stale context risks.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_doctor",
        "description": "Check MCP tools, CLI scripts, and docs/rules for drift.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_record_experiment_run",
        "description": "Record one baseline or harness run for an evidence-grade paired token experiment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "experiment_id": {"type": "string"},
                "task_fingerprint": {"type": "string"},
                "center": {"type": "string"},
                "variant": {"type": "string", "enum": ["baseline", "harness"]},
                "input_tokens": {"type": "integer"},
                "output_tokens": {"type": "integer"},
                "cost_usd": {"type": "number", "default": 0},
                "success": {"type": "boolean", "default": True},
                "quality_score": {"type": "number"},
            },
            "required": ["path", "experiment_id", "task_fingerprint", "center", "variant", "input_tokens", "output_tokens"],
        },
    },
    {
        "name": "harness_experiment_report",
        "description": "Validate paired baseline/harness runs and report token savings by center.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "quality_tolerance": {"type": "number", "default": 0.05}},
            "required": ["path"],
        },
    },
    {
        "name": "harness_init_experiment_queue",
        "description": "Initialize a reproducible tri-center baseline/harness experiment queue.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "harness_plan_next_experiment",
        "description": "Choose the next baseline or harness run using live readiness and recorded experiment runs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "queue_path": {"type": "string"},
                "experiments_path": {"type": "string"},
                "readiness": {"type": "object"},
            },
            "required": ["queue_path", "experiments_path", "readiness"],
        },
    },
    {
        "name": "harness_evaluate_experiment_output",
        "description": "Score a structured experiment output using deterministic word, citation, and risk checks.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "output": {"type": "object"}},
            "required": ["root", "output"],
        },
    },
    {
        "name": "harness_build_experiment_blueprint",
        "description": "Build a non-executing command and artifact blueprint for a queued token experiment run.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "run": {"type": "object"}},
            "required": ["root", "run"],
        },
    },
    {
        "name": "harness_prepare_experiment_run",
        "description": "Write prompt, schema, and manifest artifacts for a queued token experiment without executing it.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "run": {"type": "object"}},
            "required": ["root", "run"],
        },
    },
    {
        "name": "harness_ingest_claude_experiment",
        "description": "Parse Claude Code JSON usage, including cache token categories, into a paired experiment run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "raw_json": {"type": "string"},
                "experiment_id": {"type": "string"},
                "task_fingerprint": {"type": "string"},
                "variant": {"type": "string", "enum": ["baseline", "harness"]},
                "quality_score": {"type": "number"},
            },
            "required": ["path", "raw_json", "experiment_id", "task_fingerprint", "variant"],
        },
    },
    {
        "name": "harness_hybrid_context_pack",
        "description": "Build a compact chunk-level context pack using BM25-like ranking, path/symbol boosts, and file diversity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
                "chunk_lines": {"type": "integer", "default": 40},
                "overlap_lines": {"type": "integer", "default": 8},
            },
            "required": ["root", "query"],
        },
    },
    {
        "name": "harness_ingest_codex_experiment",
        "description": "Parse Codex --json JSONL usage into a paired token experiment; reject output with no usage event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "raw_jsonl": {"type": "string"},
                "experiment_id": {"type": "string"},
                "task_fingerprint": {"type": "string"},
                "variant": {"type": "string", "enum": ["baseline", "harness"]},
                "quality_score": {"type": "number"},
            },
            "required": ["path", "raw_jsonl", "experiment_id", "task_fingerprint", "variant"],
        },
    },
    {
        "name": "harness_init_research_registry",
        "description": "Initialize a durable official/community research source registry with refresh cadences.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "sources": {"type": "array", "items": {"type": "object"}}},
            "required": ["path", "sources"],
        },
    },
    {
        "name": "harness_due_research_sources",
        "description": "List research sources that were never checked or are stale by configured cadence.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "harness_record_source_check",
        "description": "Record a source content hash and findings so changed documentation can trigger self-growth.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "url": {"type": "string"},
                "content_hash": {"type": "string"},
                "findings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["path", "url", "content_hash"],
        },
    },
    {
        "name": "harness_refresh_research_sources",
        "description": "Fetch due registered sources, update SHA-256 baselines, and report changed pages or fetch errors.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "force": {"type": "boolean", "default": False}},
            "required": ["path"],
        },
    },
    {
        "name": "harness_plan_semantic_index",
        "description": "Plan a gated local Ollama embedding index or fall back to hybrid lexical retrieval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "machine": {"type": "object"},
                "installed_models": {"type": "array", "items": {"type": "string"}},
                "model": {"type": "string", "default": "embeddinggemma"},
            },
            "required": ["machine", "installed_models"],
        },
    },
    {
        "name": "harness_evaluate_hybrid_retrieval",
        "description": "Evaluate hybrid retrieval against a JSON dataset with Recall@K and MRR default-fail gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "dataset_path": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
                "min_recall": {"type": "number", "default": 0.8},
                "min_mrr": {"type": "number", "default": 0.5},
            },
            "required": ["root", "dataset_path"],
        },
    },
    {
        "name": "harness_readiness_report",
        "description": "Combine CLI/harness probes with quota and failure state into ready, degraded, or unavailable center status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "probes": {"type": "object"},
                "local_probe": {"type": "object"},
                "machine": {"type": "object"},
            },
            "required": ["probes"],
        },
    },
    {
        "name": "harness_compact_tool_output",
        "description": "Deduplicate repeated logs, retain high-signal lines, and hard-cap tool output before cloud handoff.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "max_chars": {"type": "integer", "default": 4000}},
            "required": ["text"],
        },
    },
    {
        "name": "harness_record_structured_handoff",
        "description": "Write a tri-center Markdown handoff plus JSON manifest with fingerprint, evidence, and context-pack references.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "from_center": {"type": "string"},
                "to_center": {"type": "string"},
                "task_fingerprint": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "context_pack": {"type": "string"},
                "open_items": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["root", "title", "summary", "from_center", "to_center", "task_fingerprint", "evidence"],
        },
    },
    {
        "name": "harness_validate_structured_handoff",
        "description": "Default-fail validation for structured handoff fields, evidence files, and context packs.",
        "inputSchema": {
            "type": "object",
            "properties": {"manifest_path": {"type": "string"}, "root": {"type": "string"}},
            "required": ["manifest_path"],
        },
    },
    {
        "name": "harness_plan_next_growth_action",
        "description": "Choose the next bounded self-growth action from integrity, retrieval, research, token experiment, and feature signals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctor": {"type": "object"},
                "readiness": {"type": "object"},
                "research": {"type": "object"},
                "retrieval_eval": {"type": "object"},
                "pending_feature": {"type": ["object", "null"]},
                "experiment_plan": {"type": ["object", "null"]},
            },
            "required": ["doctor", "readiness", "research", "retrieval_eval"],
        },
    },
    {
        "name": "harness_init_growth_campaign",
        "description": "Initialize a duration and source-coverage campaign for long-running self-growth.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "target_hours": {"type": "number"}, "required_categories": {"type": "array", "items": {"type": "string"}}},
            "required": ["path", "target_hours"],
        },
    },
    {
        "name": "harness_growth_campaign_status",
        "description": "Audit campaign elapsed wall time, cycle evidence, and provider source coverage.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "cycle_dir": {"type": "string"}},
            "required": ["path", "cycle_dir"],
        },
    },
    {
        "name": "harness_plan_local_rag_pipeline",
        "description": "Plan a gated structured local RAG map-reduce-verify pipeline or deterministic retrieval-only fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "chunk_count": {"type": "integer"},
                "machine": {"type": "object"},
                "installed_models": {"type": "array", "items": {"type": "string"}},
                "model": {"type": "string", "default": "qwen35-codex-local"},
            },
            "required": ["task", "chunk_count", "machine", "installed_models"],
        },
    },
    {
        "name": "harness_record_memory",
        "description": "Record a deduplicated local episodic/decision memory with source, tags, and importance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}, "content": {"type": "string"}, "source": {"type": "string"},
                "kind": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
                "importance": {"type": "number", "default": 0.5}
            },
            "required": ["path", "content", "source", "kind"],
        },
    },
    {
        "name": "harness_search_memory",
        "description": "Search local memories using relevance, importance, and recency scoring.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}},
            "required": ["path", "query"],
        },
    },
    {
        "name": "harness_memory_pack",
        "description": "Build a bounded source-cited memory pack before cloud reasoning.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}, "max_chars": {"type": "integer", "default": 3000}},
            "required": ["path", "query"],
        },
    },
    {
        "name": "harness_sync_artifact_memories",
        "description": "Sync structured growth cycles and handoffs into deduplicated local memory records.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "path": {"type": "string"}},
            "required": ["root", "path"],
        },
    },
    {
        "name": "harness_validate_command",
        "description": "Classify commands as ALLOW, REVIEW, or DENY before autonomous execution.",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "actor": {"type": "string", "default": "autopilot"}},
            "required": ["command"],
        },
    },
    {
        "name": "harness_evaluate_capability",
        "description": "Default-fail capability gate requiring skill, tool spec, MCP tools, docs, and evidence files.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "name": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}},
            "required": ["root", "name", "evidence"],
        },
    },
    {
        "name": "harness_promote_capability",
        "description": "Promote a draft capability to active only after its evaluation passes.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "name": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}},
            "required": ["root", "name", "evidence"],
        },
    },
    {
        "name": "harness_mcp_conformance",
        "description": "Run a subprocess JSON-RPC smoke test for initialize, tools, resources, prompts, and duplicate tool names.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_mcp_security_audit",
        "description": "Audit MCP server process-execution posture, command policy presence, and non-executing blueprints.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_context_pack_audit",
        "description": "Audit generated context packs for token budget and source provenance before cloud handoff.",
        "inputSchema": {
            "type": "object",
            "properties": {"root": {"type": "string"}, "max_chars_per_pack": {"type": "integer", "default": 12000}},
            "required": ["root"],
        },
    },
    {
        "name": "harness_codex_preflight",
        "description": "Build the compact Memory/RAG payload that must be used before sending repo-heavy work to Codex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "task": {"type": "string"},
                "memory_path": {"type": "string"},
                "max_codex_chars": {"type": "integer", "default": 6000},
            },
            "required": ["root", "task"],
        },
    },
    {
        "name": "harness_agent_rag_pack",
        "description": "Build one shared RAG context pack plus Codex, Claude Sonnet, Antigravity, and Ollama commands so every center consumes the same retrieved context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "task": {"type": "string"},
                "center": {"type": "string", "default": "project"},
                "local_model": {"type": "string"},
                "max_payload_chars": {"type": "integer", "default": 9000},
            },
            "required": ["root", "task"],
        },
    },
    {
        "name": "harness_aggregate_health",
        "description": "Aggregate tests, doctor, MCP, retrieval, research, readiness, campaign, and token experiment evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {"tests": {"type": "object"}, "doctor": {"type": "object"}, "mcp": {"type": "object"}, "retrieval": {"type": "object"}, "research": {"type": "object"}, "readiness": {"type": "object"}, "campaign": {"type": "object"}, "experiments": {"type": "object"}, "security": {"type": "object"}, "context_packs": {"type": "object"}},
            "required": ["tests", "doctor", "mcp", "retrieval", "research", "readiness", "campaign"],
        },
    },
]


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    request_id = request.get("id")
    try:
        if method == "initialize":
            requested_version = request.get("params", {}).get("protocolVersion")
            protocol_version = (
                requested_version if requested_version in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
            )
            return _ok(
                request_id,
                {
                    "protocolVersion": protocol_version,
                    "serverInfo": {"name": "tri-center-harness", "version": "0.1.0"},
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                    },
                    "instructions": (
                        "Use harness_route_task before read-heavy, multi-agent, or coding tasks. "
                        "Prefer RAG/context packs over raw file dumps. The user may switch center "
                        "between codex, claude, antigravity, or auto."
                    ),
                },
            )
        if method == "tools/list":
            return _ok(request_id, {"tools": TOOLS})
        if method == "tools/call":
            params = request.get("params", {})
            return _ok(request_id, _call_tool(params.get("name"), params.get("arguments", {})))
        if method == "resources/list":
            return _ok(request_id, {"resources": _list_resources()})
        if method == "resources/read":
            return _ok(request_id, _read_resource(request.get("params", {}).get("uri", "")))
        if method == "prompts/list":
            return _ok(request_id, {"prompts": _list_prompts()})
        if method == "prompts/get":
            params = request.get("params", {})
            return _ok(request_id, _get_prompt(params.get("name", ""), params.get("arguments", {})))
        if method == "notifications/initialized":
            return {}
        return _error(request_id, -32601, f"Unknown method: {method}")
    except Exception as exc:  # pragma: no cover - returned to MCP clients
        return _error(request_id, -32000, str(exc))


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    state = load_state(STATE_PATH)
    if name == "harness_get_status":
        return _text(state)
    if name == "harness_set_center":
        center = arguments["center"]
        state["preferred_center"] = center
        save_state(STATE_PATH, state)
        return _text({"ok": True, "preferred_center": center})
    if name == "harness_route_task":
        usage  = summarize_usage(ARTIFACTS_DIR / "usage.jsonl")
        result = choose_center(arguments["task"], state, usage_summary=usage)
        # Load per-project state if root provided
        proj_state = state
        if arguments.get("root"):
            proj_path = Path(arguments["root"]).expanduser() / ".harness" / "state.json"
            if proj_path.exists():
                proj_state = load_state(proj_path)
        result["model_tier"] = suggest_model_tier(arguments["task"], proj_state)
        return _text(result)
    if name == "harness_suggest_model_tier":
        proj_state = state
        if arguments.get("root"):
            proj_path = Path(arguments["root"]).expanduser() / ".harness" / "state.json"
            if proj_path.exists():
                proj_state = load_state(proj_path)
        return _text(suggest_model_tier(arguments["task"], proj_state))
    # ── Trajectory ────────────────────────────────────────────────────────────
    if name == "harness_begin_trajectory":
        root = Path(arguments["root"]).expanduser()
        return _text({"session_id": begin_trajectory(
            root, center=arguments["center"], model=arguments["model"], task=arguments["task"]
        )})
    if name == "harness_record_step":
        root = Path(arguments["root"]).expanduser()
        return _text(record_step(
            root, arguments["session_id"],
            tool=arguments["tool"],
            result_status=arguments["result_status"],
            args_hash=arguments.get("args_hash"),
            duration_ms=int(arguments.get("duration_ms", 0)),
            tokens=int(arguments.get("tokens", 0)),
            note=arguments.get("note", ""),
        ))
    if name == "harness_end_trajectory":
        root = Path(arguments["root"]).expanduser()
        traj = end_trajectory(
            root, arguments["session_id"],
            outcome=arguments["outcome"],
            failure_step=arguments.get("failure_step"),
        )
        # Auto-extract pattern if success
        if traj.get("outcome") == "success":
            extract_pattern_from_trajectory(root, traj)
        return _text(traj)
    if name == "harness_list_trajectories":
        root = Path(arguments["root"]).expanduser()
        return _text(list_trajectories(root, limit=int(arguments.get("limit", 20))))
    # ── Lifecycle hooks ────────────────────────────────────────────────────────
    if name == "harness_fire_event":
        root = Path(arguments["root"]).expanduser()
        return _text(fire_event(
            root, arguments["event"],
            tool=arguments["tool"],
            session_id=arguments.get("session_id"),
            center=arguments.get("center", ""),
            result_status=arguments.get("result_status", ""),
            duration_ms=int(arguments.get("duration_ms", 0)),
            tokens=int(arguments.get("tokens", 0)),
            error=arguments.get("error", ""),
        ))
    if name == "harness_register_hook":
        root = Path(arguments["root"]).expanduser()
        return _text(register_hook(
            root,
            event=arguments["event"],
            tool_pattern=arguments.get("tool_pattern", "*"),
            action=arguments["action"],
            webhook_url=arguments.get("webhook_url"),
            enabled=arguments.get("enabled", True),
        ))
    if name == "harness_list_hooks":
        return _text(list_hooks(Path(arguments["root"]).expanduser()))
    # ── Per-project growth ─────────────────────────────────────────────────────
    if name == "harness_project_growth_status":
        return _text(growth_status(Path(arguments["root"]).expanduser()))
    if name == "harness_next_project_action":
        return _text(next_project_action(Path(arguments["root"]).expanduser()))
    if name == "harness_record_routing_evidence":
        root = Path(arguments["root"]).expanduser()
        record_routing_evidence(
            root,
            center=arguments["center"],
            task_type=arguments["task_type"],
            outcome=arguments["outcome"],
            model_tier=arguments.get("model_tier", ""),
            duration_ms=int(arguments.get("duration_ms", 0)),
        )
        return _text({"recorded": True})
    if name == "harness_search_patterns":
        root = Path(arguments["root"]).expanduser()
        return _text(search_patterns(root, arguments["query"], top_k=int(arguments.get("top_k", 5))))
    # ── Telemetry ──────────────────────────────────────────────────────────────
    if name == "harness_new_chain":
        root = Path(arguments["root"]).expanduser()
        return _text({"chain_id": new_chain(root, task=arguments["task"], center=arguments["center"])})
    if name == "harness_begin_span":
        root = Path(arguments["root"]).expanduser()
        return _text({"span_id": begin_span(
            root, arguments["chain_id"],
            tool=arguments["tool"],
            depth=int(arguments.get("depth", 0)),
        )})
    if name == "harness_end_span":
        root = Path(arguments["root"]).expanduser()
        return _text(end_span(
            root, arguments["chain_id"], arguments["span_id"],
            tokens_in=int(arguments.get("tokens_in", 0)),
            tokens_out=int(arguments.get("tokens_out", 0)),
            status=arguments.get("status", "ok"),
        ))
    if name == "harness_chain_summary":
        root = Path(arguments["root"]).expanduser()
        return _text(summarize_chain(root, arguments["chain_id"]))
    if name == "harness_recent_telemetry":
        root = Path(arguments["root"]).expanduser()
        return _text(recent_telemetry(root, limit=int(arguments.get("limit", 10))))
    # ── Hack detection ─────────────────────────────────────────────────────────
    if name == "harness_check_trajectory_hacks":
        root = Path(arguments["root"]).expanduser()
        traj_dir = root / ".harness" / "trajectories"
        traj_path = traj_dir / f"{arguments['session_id']}.json"
        if not traj_path.exists():
            return _text({"error": f"trajectory not found: {arguments['session_id']}"})
        import json as _json
        traj = _json.loads(traj_path.read_text(encoding="utf-8"))
        return _text(check_trajectory(
            traj,
            prior_artifact_hash=arguments.get("prior_artifact_hash"),
            current_artifact_hash=arguments.get("current_artifact_hash"),
            prior_score=arguments.get("prior_score"),
            current_score=arguments.get("current_score"),
        ))
    if name == "harness_scan_hacks":
        root = Path(arguments["root"]).expanduser()
        return _text(scan_trajectories(root, limit=int(arguments.get("limit", 50))))
    if name == "harness_record_handoff":
        return _record_handoff(arguments)
    if name == "harness_delegate_claude":
        return _run_worker(["claude", "-p", arguments["prompt"], "--output-format", "json"], arguments, "claude")
    if name == "harness_delegate_antigravity":
        return _run_worker(["agy", "--print", arguments["prompt"]], arguments, "antigravity")
    if name == "harness_benchmark_context":
        root = Path(arguments["root"]).expanduser()
        pack = build_context_pack(root, arguments["query"], max_files=int(arguments.get("max_files", 12)))
        savings = measure_context_savings(root, pack)
        return _text({"query": arguments["query"], "root": str(root), **savings, "context_pack_preview": pack[:3000]})
    if name == "harness_init_features":
        return _text(init_feature_list(Path(arguments["path"]).expanduser(), arguments["features"]))
    if name == "harness_next_feature":
        return _text(next_feature(Path(arguments["path"]).expanduser()))
    if name == "harness_complete_feature":
        return _text(
            complete_feature(Path(arguments["path"]).expanduser(), int(arguments["feature_id"]), arguments["evidence"])
        )
    if name == "harness_evaluate_evidence":
        return _text(
            evaluate_evidence(Path(arguments["root"]).expanduser(), arguments["required"], arguments["evidence"])
        )
    if name == "harness_record_usage":
        ledger_path = Path(arguments.get("path") or ARTIFACTS_DIR / "usage.jsonl").expanduser()
        return _text(
            record_usage(
                ledger_path,
                center=arguments["center"],
                input_tokens=int(arguments["input_tokens"]),
                output_tokens=int(arguments["output_tokens"]),
                cost_usd=float(arguments["cost_usd"]),
                label=arguments.get("label"),
            )
        )
    if name == "harness_usage_report":
        return _text(summarize_usage(Path(arguments["path"]).expanduser()))
    if name == "harness_index_repo":
        return _text(build_index(Path(arguments["root"]).expanduser(), Path(arguments["index_path"]).expanduser()))
    if name == "harness_search_index":
        return _text(
            search_index(Path(arguments["index_path"]).expanduser(), arguments["query"], int(arguments.get("top_k", 5)))
        )
    if name == "harness_indexed_context_pack":
        return _text(
            {
                "context_pack": build_indexed_context_pack(
                    Path(arguments["root"]).expanduser(),
                    Path(arguments["index_path"]).expanduser(),
                    arguments["query"],
                    top_k=int(arguments.get("top_k", 5)),
                    max_chars_per_file=int(arguments.get("max_chars_per_file", 1200)),
                )
            }
        )
    if name == "harness_contextual_context_pack":
        return _text(
            {
                "context_pack": build_contextual_context_pack(
                    Path(arguments["root"]).expanduser(),
                    arguments["query"],
                    top_k=int(arguments.get("top_k", 5)),
                    max_chars_per_chunk=int(arguments.get("max_chars_per_chunk", 1200)),
                )
            }
        )
    if name == "harness_local_context_pack":
        return _text(_local_context_pack(
            Path(arguments["root"]).expanduser(),
            arguments["query"],
            top_k=int(arguments.get("top_k", 6)),
            max_chars_per_chunk=int(arguments.get("max_chars_per_chunk", 1200)),
            max_summary_chars=int(arguments.get("max_summary_chars", 3000)),
        ))
    if name == "harness_init_project":
        return _text(init_project_harness(Path(arguments["root"]).expanduser(), arguments["features"]))
    if name == "harness_analyze_project":
        return _text(analyze_project(Path(arguments["root"]).expanduser().resolve()))
    if name == "harness_init_full":
        return _text(
            init_project_full(
                Path(arguments["root"]).expanduser().resolve(),
                Path(arguments["harness_root"]).expanduser().resolve(),
                arguments["analysis"],
                dry_run=bool(arguments.get("dry_run", False)),
                skip_index=bool(arguments.get("skip_index", False)),
            )
        )
    if name == "harness_grill_project":
        root = Path(arguments["root"]).expanduser().resolve()
        answers = arguments.get("answers")
        if answers:
            harness_md = root / "HARNESS.md"
            write_grill_answers_to_harness_md(harness_md, answers)
            return _text({"updated": str(harness_md), "keys": list(answers.keys())})
        project_json = root / ".harness" / "project.json"
        if project_json.exists():
            import json as _json
            meta = _json.loads(project_json.read_text(encoding="utf-8"))
            lang, fw = meta.get("language", "unknown"), meta.get("framework", "")
        else:
            a = analyze_project(root)
            lang, fw = a["language"], a["framework"]
        return _text({"questions": generate_grill_questions(lang, fw)})
    if name == "harness_local_model_gate":
        return _text(local_model_decision(arguments["machine"], arguments["task_complexity"]))
    if name == "harness_plan_local_worker":
        return _text(
            plan_local_worker(
                arguments["task"],
                machine=arguments["machine"],
                task_complexity=arguments["task_complexity"],
                model=arguments.get("model", "qwen35-codex-local"),
            )
        )
    if name == "harness_plan_structured_local_worker":
        return _text(
            plan_structured_local_worker(
                arguments["task"],
                machine=arguments["machine"],
                task_complexity=arguments["task_complexity"],
                schema=arguments["schema"],
                model=arguments.get("model", "qwen35-codex-local"),
            )
        )
    if name == "harness_scaffold_capability":
        return _text(
            scaffold_capability(Path(arguments["root"]).expanduser(), arguments["name"], arguments["description"])
        )
    if name == "harness_list_capabilities":
        return _text(list_capabilities(Path(arguments["root"]).expanduser()))
    if name == "harness_run_growth_cycle":
        return _text(
            run_growth_cycle(
                Path(arguments["root"]).expanduser(),
                topic=arguments["topic"],
                sources=arguments["sources"],
                actions=arguments["actions"],
            )
        )
    if name == "harness_run_evaluated_growth_cycle":
        return _text(
            run_evaluated_growth_cycle(
                Path(arguments["root"]).expanduser(),
                topic=arguments["topic"],
                sources=arguments["sources"],
                actions=arguments["actions"],
                usage=arguments["usage"],
                required_evidence=arguments["required_evidence"],
            )
        )
    if name == "harness_audit_handoffs":
        return _text(audit_handoffs(Path(arguments["root"]).expanduser()))
    if name == "harness_doctor":
        return _text(run_harness_doctor(Path(arguments["root"]).expanduser()))
    if name == "harness_record_experiment_run":
        return _text(
            record_experiment_run(
                Path(arguments["path"]).expanduser(),
                experiment_id=arguments["experiment_id"],
                task_fingerprint=arguments["task_fingerprint"],
                center=arguments["center"],
                variant=arguments["variant"],
                input_tokens=int(arguments["input_tokens"]),
                output_tokens=int(arguments["output_tokens"]),
                cost_usd=float(arguments.get("cost_usd", 0)),
                success=bool(arguments.get("success", True)),
                quality_score=arguments.get("quality_score"),
            )
        )
    if name == "harness_experiment_report":
        return _text(
            summarize_experiments(
                Path(arguments["path"]).expanduser(),
                quality_tolerance=float(arguments.get("quality_tolerance", 0.05)),
            )
        )
    if name == "harness_ingest_claude_experiment":
        return _text(
            ingest_claude_result(
                Path(arguments["path"]).expanduser(),
                arguments["raw_json"],
                experiment_id=arguments["experiment_id"],
                task_fingerprint=arguments["task_fingerprint"],
                variant=arguments["variant"],
                quality_score=arguments.get("quality_score"),
            )
        )
    if name == "harness_hybrid_context_pack":
        return _text(
            {
                "context_pack": build_hybrid_context_pack(
                    Path(arguments["root"]).expanduser(),
                    arguments["query"],
                    top_k=int(arguments.get("top_k", 5)),
                    chunk_lines=int(arguments.get("chunk_lines", 40)),
                    overlap_lines=int(arguments.get("overlap_lines", 8)),
                )
            }
        )
    if name == "harness_ingest_codex_experiment":
        return _text(
            ingest_codex_jsonl(
                Path(arguments["path"]).expanduser(),
                arguments["raw_jsonl"],
                experiment_id=arguments["experiment_id"],
                task_fingerprint=arguments["task_fingerprint"],
                variant=arguments["variant"],
                quality_score=arguments.get("quality_score"),
            )
        )
    if name == "harness_init_research_registry":
        return _text(init_research_registry(Path(arguments["path"]).expanduser(), arguments["sources"]))
    if name == "harness_due_research_sources":
        return _text(due_research_sources(Path(arguments["path"]).expanduser()))
    if name == "harness_record_source_check":
        return _text(
            record_source_check(
                Path(arguments["path"]).expanduser(),
                arguments["url"],
                content_hash=arguments["content_hash"],
                findings=arguments.get("findings"),
            )
        )
    if name == "harness_refresh_research_sources":
        return _text(
            refresh_research_sources(
                Path(arguments["path"]).expanduser(),
                force=bool(arguments.get("force", False)),
            )
        )
    if name == "harness_plan_semantic_index":
        return _text(
            plan_semantic_index(
                machine=arguments["machine"],
                installed_models=arguments["installed_models"],
                model=arguments.get("model", "embeddinggemma"),
            )
        )
    if name == "harness_evaluate_hybrid_retrieval":
        return _text(
            evaluate_hybrid_dataset(
                Path(arguments["root"]).expanduser(),
                Path(arguments["dataset_path"]).expanduser(),
                top_k=int(arguments.get("top_k", 5)),
                min_recall=float(arguments.get("min_recall", 0.8)),
                min_mrr=float(arguments.get("min_mrr", 0.5)),
            )
        )
    if name == "harness_readiness_report":
        return _text(
            build_readiness_report(
                state,
                probes=arguments["probes"],
                local_probe=arguments.get("local_probe"),
                machine=arguments.get("machine"),
            )
        )
    if name == "harness_compact_tool_output":
        return _text(compact_tool_output(arguments["text"], max_chars=int(arguments.get("max_chars", 4000))))
    if name == "harness_record_structured_handoff":
        return _text(
            write_structured_handoff(
                Path(arguments["root"]).expanduser(),
                title=arguments["title"],
                summary=arguments["summary"],
                from_center=arguments["from_center"],
                to_center=arguments["to_center"],
                task_fingerprint=arguments["task_fingerprint"],
                evidence=arguments["evidence"],
                context_pack=arguments.get("context_pack"),
                open_items=arguments.get("open_items"),
            )
        )
    if name == "harness_validate_structured_handoff":
        return _text(
            validate_structured_handoff(
                Path(arguments["manifest_path"]).expanduser(),
                root=Path(arguments["root"]).expanduser() if arguments.get("root") else None,
            )
        )
    if name == "harness_plan_next_growth_action":
        return _text(
            plan_next_growth_action(
                doctor=arguments["doctor"],
                readiness=arguments["readiness"],
                research=arguments["research"],
                retrieval_eval=arguments["retrieval_eval"],
                pending_feature=arguments.get("pending_feature"),
                experiment_plan=arguments.get("experiment_plan"),
            )
        )
    if name == "harness_init_growth_campaign":
        return _text(
            init_campaign(
                Path(arguments["path"]).expanduser(),
                target_hours=float(arguments["target_hours"]),
                required_categories=arguments.get("required_categories"),
            )
        )
    if name == "harness_growth_campaign_status":
        return _text(
            campaign_status(
                Path(arguments["path"]).expanduser(),
                cycle_dir=Path(arguments["cycle_dir"]).expanduser(),
            )
        )
    if name == "harness_plan_local_rag_pipeline":
        return _text(
            plan_local_rag_pipeline(
                arguments["task"],
                chunk_count=int(arguments["chunk_count"]),
                machine=arguments["machine"],
                installed_models=arguments["installed_models"],
                model=arguments.get("model", "qwen35-codex-local"),
            )
        )
    if name == "harness_record_memory":
        return _text(record_memory(Path(arguments["path"]).expanduser(), content=arguments["content"], source=arguments["source"], kind=arguments["kind"], tags=arguments.get("tags"), importance=float(arguments.get("importance", 0.5))))
    if name == "harness_search_memory":
        return _text(search_memories(Path(arguments["path"]).expanduser(), arguments["query"], top_k=int(arguments.get("top_k", 5))))
    if name == "harness_memory_pack":
        return _text({"memory_pack": build_memory_pack(Path(arguments["path"]).expanduser(), arguments["query"], top_k=int(arguments.get("top_k", 5)), max_chars=int(arguments.get("max_chars", 3000)))})
    if name == "harness_sync_artifact_memories":
        return _text(sync_artifact_memories(Path(arguments["root"]).expanduser(), Path(arguments["path"]).expanduser()))
    if name == "harness_validate_command":
        return _text(validate_command(arguments["command"], actor=arguments.get("actor", "autopilot")))
    if name == "harness_evaluate_capability":
        return _text(evaluate_capability(Path(arguments["root"]).expanduser(), arguments["name"], evidence=arguments["evidence"]))
    if name == "harness_promote_capability":
        return _text(promote_capability(Path(arguments["root"]).expanduser(), arguments["name"], evidence=arguments["evidence"]))
    if name == "harness_mcp_conformance":
        root = Path(arguments["root"]).expanduser()
        return _text(run_mcp_conformance(root / "scripts" / "harness-mcp-server", cwd=root))
    if name == "harness_mcp_security_audit":
        root = Path(arguments["root"]).expanduser()
        return _text(audit_mcp_security(server_text=(root / "harness_mcp" / "server.py").read_text(encoding="utf-8"), tools=TOOLS))
    if name == "harness_context_pack_audit":
        return _text(audit_context_packs(Path(arguments["root"]).expanduser(), max_chars_per_pack=int(arguments.get("max_chars_per_pack", 12000))))
    if name == "harness_codex_preflight":
        root = Path(arguments["root"]).expanduser()
        memory_path = Path(arguments.get("memory_path") or root / ".harness" / "memory.jsonl").expanduser()
        return _text(build_codex_preflight(root, arguments["task"], memory_path=memory_path, max_codex_chars=int(arguments.get("max_codex_chars", 6000))))
    if name == "harness_agent_rag_pack":
        return _text(
            build_agent_rag_pack(
                Path(arguments["root"]).expanduser(),
                arguments["task"],
                center=arguments.get("center", "project"),
                local_model=arguments.get("local_model"),
                max_payload_chars=int(arguments.get("max_payload_chars", 9000)),
            )
        )
    if name == "harness_aggregate_health":
        return _text(aggregate_health(tests=arguments["tests"], doctor=arguments["doctor"], mcp=arguments["mcp"], retrieval=arguments["retrieval"], research=arguments["research"], readiness=arguments["readiness"], campaign=arguments["campaign"], experiments=arguments.get("experiments"), security=arguments.get("security"), context_packs=arguments.get("context_packs")))
    if name == "harness_init_experiment_queue":
        return _text(init_experiment_queue(Path(arguments["path"]).expanduser()))
    if name == "harness_plan_next_experiment":
        return _text(plan_next_experiment(Path(arguments["queue_path"]).expanduser(), Path(arguments["experiments_path"]).expanduser(), arguments["readiness"]))
    if name == "harness_evaluate_experiment_output":
        return _text(evaluate_experiment_output(Path(arguments["root"]).expanduser(), arguments["output"]))
    if name == "harness_build_experiment_blueprint":
        return _text(build_experiment_blueprint(Path(arguments["root"]).expanduser(), arguments["run"]))
    if name == "harness_prepare_experiment_run":
        return _text(prepare_experiment_run(Path(arguments["root"]).expanduser(), arguments["run"]))
    raise ValueError(f"Unknown tool: {name}")


def _list_resources() -> list[dict[str, Any]]:
    resources = [{"uri": "harness://state", "name": "Harness state", "mimeType": "application/json"}]
    rules_dir = ROOT / "rules"
    if rules_dir.exists():
        for path in sorted(rules_dir.glob("*.md")):
            resources.append(
                {
                    "uri": f"harness://rules/{path.name}",
                    "name": f"Harness rule: {path.name}",
                    "mimeType": "text/markdown",
                }
            )
    feature_path = ARTIFACTS_DIR / "feature_list.json"
    if feature_path.exists():
        resources.append({"uri": "harness://features/current", "name": "Current feature list", "mimeType": "application/json"})
    return resources


def _read_resource(uri: str) -> dict[str, Any]:
    if uri == "harness://state":
        text = json.dumps(load_state(STATE_PATH), indent=2, ensure_ascii=False)
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": text}]}
    if uri.startswith("harness://rules/"):
        name = uri.rsplit("/", 1)[-1]
        path = ROOT / "rules" / name
        if not path.exists():
            raise ValueError(f"Unknown rule resource: {uri}")
        return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": path.read_text(encoding="utf-8")}]}
    if uri == "harness://features/current":
        path = ARTIFACTS_DIR / "feature_list.json"
        if not path.exists():
            raise ValueError("No current feature list")
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": path.read_text(encoding="utf-8")}]}
    raise ValueError(f"Unknown resource: {uri}")


def _list_prompts() -> list[dict[str, Any]]:
    return [
        {
            "name": "self_growth_cycle",
            "description": "Run one evidence-backed self-growth cycle for a harness topic.",
            "arguments": [{"name": "topic", "required": True}],
        },
        {
            "name": "context_pack_first",
            "description": "Build or request a compact context pack before cloud reasoning.",
            "arguments": [{"name": "task", "required": True}],
        },
        {
            "name": "fresh_evaluator",
            "description": "Evaluate work from fresh context using required evidence.",
            "arguments": [{"name": "required_evidence", "required": True}],
        },
    ]


def _get_prompt(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "self_growth_cycle":
        topic = arguments.get("topic", "harness")
        text = (
            f"Run one self-growth cycle for {topic}. First route the task through harness_route_task, "
            "then gather current sources, propose one small capability improvement, write tests first, "
            "implement, run tests, record usage, and evaluate evidence before marking done."
        )
    elif name == "context_pack_first":
        task = arguments.get("task", "the task")
        text = (
            f"For {task}, avoid raw repo dumps. Build an indexed context pack, benchmark token savings, "
            "then send only the compact pack plus file references to the selected center."
        )
    elif name == "fresh_evaluator":
        required = arguments.get("required_evidence", "tests passed, handoff recorded")
        text = (
            f"Evaluate from fresh context. Required evidence: {required}. Return PASS only if every item is present; "
            "otherwise return NEEDS_WORK with missing evidence."
        )
    else:
        raise ValueError(f"Unknown prompt: {name}")
    return {
        "description": name,
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }


def _record_handoff(arguments: dict[str, Any]) -> dict[str, Any]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "-" for ch in arguments["title"].lower()).strip("-")[:80]
    path = ARTIFACTS_DIR / "handoffs" / f"{slug or 'handoff'}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    center = arguments.get("center", "shared")
    path.write_text(f"# {arguments['title']}\n\ncenter: {center}\n\n{arguments['body']}\n", encoding="utf-8")
    return _text({"ok": True, "path": str(path)})


def _run_worker(command: list[str], arguments: dict[str, Any], center: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '')}"
    timeout = int(arguments.get("timeout_sec", 300))
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        state = load_state(STATE_PATH)
        updated_state = apply_worker_feedback(
            state,
            center=center,
            returncode=124,
            output=f"worker timed out after {timeout}s",
        )
        save_state(STATE_PATH, updated_state)
        return _text({"ok": False, "error": f"worker timed out after {timeout}s", "command": command[0]})
    output = f"{completed.stdout}\n{completed.stderr}"
    state = load_state(STATE_PATH)
    updated_state = apply_worker_feedback(
        state,
        center=center,
        returncode=completed.returncode,
        output=output,
    )
    if updated_state != state:
        save_state(STATE_PATH, updated_state)
    return _text(
        {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-4000:],
        }
    )


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}


def _ok(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _local_context_pack(
    root: Path,
    query: str,
    *,
    top_k: int = 6,
    max_chars_per_chunk: int = 1200,
    max_summary_chars: int = 3000,
) -> dict[str, Any]:
    """Retrieve context with BM25, then optionally summarise via local LLM sub-agent."""
    from harness_core.contextual_chunks import build_contextual_context_pack

    # Read local LLM config
    project_json = root / ".harness" / "project.json"
    llm_cfg: dict[str, Any] = {}
    if project_json.exists():
        try:
            meta = json.loads(project_json.read_text(encoding="utf-8"))
            llm_cfg = meta.get("local_llm", {})
        except Exception:
            pass

    raw_pack = build_contextual_context_pack(root, query, top_k=top_k,
                                             max_chars_per_chunk=max_chars_per_chunk)

    if not llm_cfg.get("enabled") or not llm_cfg.get("model"):
        return {"context_pack": raw_pack, "source": "bm25", "local_llm": None}

    model  = llm_cfg["model"]
    host   = llm_cfg.get("host", "http://localhost:11434").rstrip("/")
    prompt = (
        f"You are a context retrieval sub-agent. "
        f"Given the query and code context below, extract and summarise "
        f"only the parts directly relevant to the query. "
        f"Be concise — target {max_summary_chars} characters max.\n\n"
        f"Query: {query}\n\n"
        f"Context:\n{raw_pack[:8000]}"
    )
    try:
        import urllib.request as _ur
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_summary_chars // 3},
        }).encode("utf-8")
        req = _ur.Request(f"{host}/api/generate", data=payload,
                          headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        summary = data.get("response", "").strip()
        if summary:
            return {
                "context_pack": summary,
                "source": "local_llm",
                "local_llm": model,
                "raw_chars": len(raw_pack),
                "summary_chars": len(summary),
            }
    except Exception as exc:
        pass  # fall back to raw BM25 pack on any Ollama error

    return {"context_pack": raw_pack, "source": "bm25_fallback", "local_llm": model}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def main() -> None:
    if not STATE_PATH.exists():
        save_state(STATE_PATH, default_state())
    for line in sys.stdin:
        if not line.strip():
            continue
        response = dispatch(json.loads(line))
        if response:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
