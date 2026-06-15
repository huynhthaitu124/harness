from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_core.feature_state import init_feature_list
from harness_core.lifecycle import default_hooks, save_hooks
from harness_core.project_growth import bootstrap_growth
from harness_core.project_analyzer import (
    build_analysis_context,
    detect_agents,
    detect_project_type,
    extract_key_files,
    generate_initial_features,
    generate_initial_memories,
    generate_mcp_config,
    generate_routing_keywords,
    render_harness_html,
    render_harness_md,
    seed_memories,
)
from harness_core.router import default_state, save_state
from harness_core.search_index import build_index

# ── Agent instruction files that each tool reads at session start ─────────────
_AGENT_INSTRUCTION_FILES = [
    "CLAUDE.md",   # Claude Code
    "AGENTS.md",   # Codex
    "GEMINI.md",   # Antigravity / Gemini CLI
]

_HARNESS_BLOCK_START = "<!-- harness:start -->"
_HARNESS_BLOCK_END   = "<!-- harness:end -->"


def _harness_instruction_block(root: Path) -> str:
    """Return the mandatory harness block to inject into agent instruction files."""
    return f"""{_HARNESS_BLOCK_START}
## Harness — Mandatory First Step

For **every task, bug, or ticket** you receive in this project — regardless of how it arrives:

1. **First tool call** must be `harness_ticket_context` (MCP):
   - `root`: `{root}`
   - `task`: the user's message or ticket description verbatim

2. **If MCP is unavailable**, run this CLI command first:
   ```bash
   harness rag-pack "<task description>" [--ticket <id>]
   ```
   Then read `.harness/context_packs/last-rag-pack.md` before opening any source file.

3. **Never** call `list_dir`, `read_file`, `grep_search`, `find`, or any file-reading tool
   on source code until you have the Harness context pack. The pack tells you exactly
   which files to open — cold exploration wastes tokens and misses conventions.

Project root : `{root}`
HARNESS.html : `{root}/HARNESS.html` (architecture, modules, conventions, ticket workflow)
{_HARNESS_BLOCK_END}"""


def inject_agent_instructions(root: Path) -> list[str]:
    """Write or update the mandatory harness block in CLAUDE.md, AGENTS.md, GEMINI.md.

    If the file already exists, replaces the block between the harness markers.
    If the file doesn't exist yet, creates it with just the harness block so the
    project owner can add more content later.

    Returns list of files that were written or updated.
    """
    block   = _harness_instruction_block(root)
    updated = []

    for filename in _AGENT_INSTRUCTION_FILES:
        path = root / filename
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8")
                if _HARNESS_BLOCK_START in content:
                    # Replace existing block
                    start = content.index(_HARNESS_BLOCK_START)
                    end   = content.index(_HARNESS_BLOCK_END) + len(_HARNESS_BLOCK_END)
                    new_content = content[:start] + block + content[end:]
                else:
                    # Append block at end
                    new_content = content.rstrip("\n") + "\n\n" + block + "\n"
                path.write_text(new_content, encoding="utf-8")
            else:
                # Create minimal file — owner adds project-specific content above
                path.write_text(block + "\n", encoding="utf-8")
            updated.append(filename)
        except Exception:
            pass  # never fail init due to instruction injection

    return updated


def init_project_harness(root: Path, features: list[str]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    feature_path = root / "feature_list.json"
    init_feature_list(feature_path, features)

    init_script = root / "init.sh"
    init_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo \"Harness project init\"\n"
        "test -f feature_list.json\n",
        encoding="utf-8",
    )
    init_script.chmod(0o755)

    handoff_dir = root / "production_artifacts" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "README.md").write_text(
        "# Handoffs\n\nWrite compact center-to-center handoffs here.\n",
        encoding="utf-8",
    )
    (root / "production_artifacts" / "context_packs").mkdir(parents=True, exist_ok=True)
    (root / "production_artifacts" / "evaluations").mkdir(parents=True, exist_ok=True)
    return {
        "root": str(root),
        "feature_list": str(feature_path),
        "init_script": str(init_script),
        "feature_count": len(features),
    }


def analyze_project(target_root: Path) -> dict[str, Any]:
    project_type = detect_project_type(target_root)
    key_files    = extract_key_files(target_root)
    context_snippet = build_analysis_context(target_root, key_files)
    keywords = generate_routing_keywords(
        project_type["language"],
        project_type["framework"],
    )
    features = generate_initial_features(project_type["language"])
    memories = generate_initial_memories({**project_type}, target_root)
    agents   = detect_agents(target_root)
    return {
        **project_type,
        "project_name":    target_root.name,
        "key_files":       [str(p) for p in key_files],
        "context_snippet": context_snippet,
        "routing_keywords": keywords,
        "initial_features": features,
        "initial_memories": memories,
        "agents":          agents,
    }


def init_project_full(
    target_root: Path,
    harness_root: Path,
    analysis: dict[str, Any],
    *,
    dry_run: bool = False,
    skip_index: bool = False,
    agent_sections: "dict[str, Any] | None" = None,
) -> dict[str, Any]:
    created: list[str] = []

    def _write(path: Path, text: str) -> None:
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        created.append(str(path))

    def _mkdir(path: Path) -> None:
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)

    # All harness data lives under .harness/ — nothing scattered at project root
    hd = target_root / ".harness"

    # ── core config ────────────────────────────────────────────────────────────
    state = default_state()
    state["routing_policy"].update(analysis.get("routing_keywords", {}))
    state_path = hd / "state.json"
    if not dry_run:
        save_state(state_path, state)
    created.append(str(state_path))

    import datetime as _dt
    project_meta = {
        "project_name":        analysis.get("project_name", target_root.name),
        "language":            analysis.get("language", "unknown"),
        "framework":           analysis.get("framework", ""),
        "secondary_languages": analysis.get("secondary_languages", []),
        "config_file":         analysis.get("config_file", ""),
        "entry_points":        analysis.get("entry_points", []),
        "agents":              analysis.get("agents", []),
        "harness_root":        str(harness_root),
        "analyzed_at":         _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    _write(hd / "project.json", json.dumps(project_meta, indent=2, ensure_ascii=False) + "\n")

    # ── BM25 index ────────────────────────────────────────────────────────────
    index_path = hd / "index.json"
    if not skip_index and not dry_run:
        build_index(target_root, index_path)
    created.append(str(index_path))

    # ── memory ────────────────────────────────────────────────────────────────
    memory_path = hd / "memory.jsonl"
    if not dry_run:
        seed_memories(memory_path, analysis.get("initial_memories", []))
    created.append(str(memory_path))

    # ── artifact subdirs ──────────────────────────────────────────────────────
    for subdir in ("handoffs", "context_packs", "evaluations"):
        _mkdir(hd / subdir)
        created.append(str(hd / subdir))

    _write(hd / "handoffs" / "README.md",
           "# Handoffs\n\nWrite compact center-to-center handoffs here.\n")

    feature_path = hd / "feature_list.json"
    if not dry_run:
        init_feature_list(feature_path, analysis.get("initial_features", []))
    created.append(str(feature_path))

    # ── MCP config ────────────────────────────────────────────────────────────
    mcp_config = generate_mcp_config(harness_root, target_root)
    _write(hd / "mcp.json", json.dumps(mcp_config, indent=2, ensure_ascii=False) + "\n")

    # ── lifecycle hooks ───────────────────────────────────────────────────────
    if not dry_run:
        save_hooks(target_root, default_hooks())

    # ── per-project self-growth bootstrap ─────────────────────────────────────
    if not dry_run:
        bootstrap_growth(target_root, analysis.get("initial_features", []))

    # ── docs at project root (agents + browser need these at root) ────────────
    project_name = analysis.get("project_name", target_root.name)
    _write(target_root / "HARNESS.md",
           render_harness_md(analysis, harness_root / "scripts", project_name))

    # ── inject mandatory first-call rule into agent instruction files ─────────
    if not dry_run:
        inject_agent_instructions(target_root)

    # ── save agent research if provided ──────────────────────────────────────
    if agent_sections and not dry_run:
        from harness_core.agent_research import save_research
        save_research(target_root, agent_sections)

    # ── load workflow if it exists ────────────────────────────────────────────
    from harness_core.workflow_steps import load_workflow
    workflow = load_workflow(target_root)

    _write(target_root / "HARNESS.html",
           render_harness_html(analysis, project_name, harness_root / "scripts",
                               agent_sections=agent_sections, workflow=workflow))

    return {
        "root":        str(target_root),
        "harness_dir": str(hd),
        "dry_run":     dry_run,
        "analysis":    {k: v for k, v in analysis.items() if k != "initial_memories"},
        "created":     created,
    }
