"""Generate MCP schema documentation from the live TOOLS list in server.py.

Produces two outputs:
  1. .harness/mcp_schema.md   — full tiered reference for agents to read
  2. A compact Tier-1 block   — embedded in CLAUDE.md / AGENTS.md / GEMINI.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# ── Tool tiers ────────────────────────────────────────────────────────────────
# Each tier has a heading, a description of when to use it, and a list of
# tool names that belong here.  Names not listed fall into "Advanced".

_TIERS: list[dict[str, Any]] = [
    {
        "heading": "Tier 1 — Work loop (non-fast tasks)",
        "note": "Fast tasks may proceed directly. For light/deep tasks, locate context first, then read real files before editing.",
        "tools": [
            "harness_ticket_context",
            "harness_route_task",
            "harness_locate_context",
            "harness_contextual_context_pack",
            "harness_hybrid_context_pack",
            "harness_search_memory",
            "harness_memory_pack",
            "harness_record_memory",
        ],
    },
    {
        "heading": "Tier 2 — Context & indexing (targeted retrieval)",
        "note": "Use when Tier 1 context isn't enough or you need a different retrieval angle.",
        "tools": [
            "harness_search_index",
            "harness_indexed_context_pack",
            "harness_local_context_pack",
            "harness_agent_rag_pack",
            "harness_local_model_gate",
        ],
    },
    {
        "heading": "Tier 3 — Routing & status",
        "note": "Check readiness before long tasks; update center when switching work type.",
        "tools": [
            "harness_get_status",
            "harness_set_center",
            "harness_suggest_model_tier",
            "harness_readiness_report",
            "harness_aggregate_health",
        ],
    },
    {
        "heading": "Tier 4 — Handoffs & telemetry",
        "note": "Record what you did so the next agent (or session) starts with full context.",
        "tools": [
            "harness_record_structured_handoff",
            "harness_validate_structured_handoff",
            "harness_audit_handoffs",
            "harness_record_handoff",
            "harness_begin_trajectory",
            "harness_record_step",
            "harness_end_trajectory",
            "harness_list_trajectories",
            "harness_new_chain",
            "harness_begin_span",
            "harness_end_span",
            "harness_chain_summary",
            "harness_recent_telemetry",
        ],
    },
    {
        "heading": "Tier 5 — Init & admin (once per project)",
        "note": "Run during harness init or when rebuilding the index.",
        "tools": [
            "harness_analyze_project",
            "harness_init_full",
            "harness_init_project",
            "harness_index_repo",
            "harness_grill_project",
            "harness_doctor",
            "harness_context_pack_audit",
            "harness_mcp_conformance",
            "harness_mcp_security_audit",
        ],
    },
    {
        "heading": "Tier 6 — Growth & experimentation (autonomous improvement)",
        "note": "Used by the harness self-growth loop; rarely called directly.",
        "tools": [
            "harness_project_growth_status",
            "harness_next_project_action",
            "harness_init_growth_campaign",
            "harness_growth_campaign_status",
            "harness_plan_next_growth_action",
            "harness_run_growth_cycle",
            "harness_run_evaluated_growth_cycle",
            "harness_record_routing_evidence",
            "harness_search_patterns",
            "harness_check_trajectory_hacks",
            "harness_scan_hacks",
            "harness_record_experiment_run",
            "harness_experiment_report",
            "harness_record_usage",
            "harness_usage_report",
            "harness_evaluate_evidence",
            "harness_evaluate_capability",
            "harness_promote_capability",
            "harness_scaffold_capability",
            "harness_list_capabilities",
        ],
    },
]


def _load_tools(harness_root: Path) -> list[dict[str, Any]]:
    """Import TOOLS from server.py at runtime to stay in sync."""
    import importlib.util
    import sys

    server_path = harness_root / "harness_mcp" / "server.py"
    spec = importlib.util.spec_from_file_location("_harness_server_tmp", server_path)
    mod  = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["_harness_server_tmp"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.TOOLS


def _tool_row(tool: dict[str, Any]) -> str:
    name  = tool["name"]
    desc  = tool.get("description", "").split(".")[0].rstrip()
    props = tool.get("inputSchema", {}).get("properties", {})
    req   = set(tool.get("inputSchema", {}).get("required", []))
    params = ", ".join(
        (f"`{k}`" if k in req else f"`{k}?`")
        for k in props
    )
    return f"| `{name}` | {params} | {desc} |"


def generate_mcp_schema_md(harness_root: Path, project_name: str = "") -> str:
    """Return the full .harness/mcp_schema.md content."""
    try:
        tools = _load_tools(harness_root)
    except Exception as exc:
        return f"# Harness MCP Schema\n\n_Error loading tools: {exc}_\n"

    by_name = {t["name"]: t for t in tools}

    lines: list[str] = []
    header = f"# Harness MCP Tools{' — ' + project_name if project_name else ''}"
    lines += [
        header,
        "",
        "Generated by `harness init` / `harness mcp register`.  "
        "Use `harness mcp register` to refresh after a harness upgrade.",
        "",
        f"Server: `harness-mcp-server` (tri-center-harness)  |  {len(tools)} tools total",
        "",
    ]

    all_tiered: set[str] = set()
    for tier in _TIERS:
        lines += [f"## {tier['heading']}", "", f"_{tier['note']}_", ""]
        lines += ["| Tool | Parameters | What it does |", "|------|-----------|-------------|"]
        for tname in tier["tools"]:
            t = by_name.get(tname)
            if t:
                lines.append(_tool_row(t))
                all_tiered.add(tname)
        lines.append("")

    # Remaining tools not assigned to a tier
    remaining = [t for t in tools if t["name"] not in all_tiered]
    if remaining:
        lines += [
            "## Other tools",
            "",
            "| Tool | Parameters | What it does |",
            "|------|-----------|-------------|",
        ]
        for t in remaining:
            lines.append(_tool_row(t))
        lines.append("")

    lines += [
        "---",
        "",
        "## Parameter notes",
        "",
        "- `root` — absolute path to the project root (e.g. `/Users/you/Projects/my-app`)",
        "- `task` — the user's message or ticket description, verbatim",
        "- `ticket_id` — optional ticket reference (e.g. `WT-102`, `OP-456`); used to key the RAG pack file",
        "- `top_k` — number of RAG chunks to return (default 5)",
        "- `query` — retrieval query (can differ from `task` for more targeted results)",
        "",
        "## Call order for a typical task",
        "",
        "```",
        "1. harness_ticket_context(root, task, ticket_id?)   ← replaces cold file exploration",
        "2. harness_search_memory(root, query)               ← check prior decisions",
        "3. [implement using only files the context pack named]",
        "4. harness_record_memory(root, content)             ← save key insight",
        "5. harness_record_structured_handoff(...)           ← if handing off to another center",
        "```",
        "",
    ]
    return "\n".join(lines)


def generate_compact_tier1_md(harness_root: Path, schema_path: Path) -> str:
    """Return the compact Tier-1 block to embed in agent instruction files."""
    try:
        tools = _load_tools(harness_root)
    except Exception:
        tools = []

    tier1_names = _TIERS[0]["tools"]
    by_name     = {t["name"]: t for t in tools}

    rows: list[str] = []
    for name in tier1_names:
        t = by_name.get(name)
        if not t:
            continue
        props = t.get("inputSchema", {}).get("properties", {})
        req   = set(t.get("inputSchema", {}).get("required", []))
        params = ", ".join(
            (f"`{k}`" if k in req else f"`{k}?`")
            for k in props
        )
        desc = t.get("description", "").split(".")[0].rstrip()
        rows.append(f"| `{name}` | {params} | {desc} |")

    table = "\n".join(
        ["| Tool | Parameters | When to use |", "|------|-----------|-------------|"]
        + rows
    )

    return f"""### Available MCP tools (Tier 1 — light/deep work loop)

Fast tasks with exact files can proceed directly. For light/deep tasks, use locator/context tools as navigation, then read the real files before editing.

{table}

Full tool reference (all {len(tools)} tools, grouped by tier):
`{schema_path}`"""


def write_mcp_schema(target_root: Path, harness_root: Path) -> Path:
    """Write .harness/mcp_schema.md and return its path."""
    schema_path = target_root / ".harness" / "mcp_schema.md"
    project_name = target_root.name
    content = generate_mcp_schema_md(harness_root, project_name)
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(content, encoding="utf-8")
    return schema_path
