from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_core.feature_state import init_feature_list
from harness_core.lifecycle import default_hooks, save_hooks
from harness_core.project_growth import bootstrap_growth
from harness_core.project_analyzer import (
    build_analysis_context,
    build_doc_context,
    detect_agents,
    detect_project_type,
    extract_doc_files,
    extract_key_files,
    generate_agents_md,
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
    "CODEX.md",    # Codex (alternative name)
    "GEMINI.md",   # Antigravity / Gemini CLI
]

_HARNESS_BLOCK_START = "<!-- harness:start -->"
_HARNESS_BLOCK_END   = "<!-- harness:end -->"


def _harness_instruction_block(root: Path, harness_root: Path | None = None) -> str:
    """Return the mandatory harness block to inject into agent instruction files."""
    harness_md = root / "HARNESS.md"
    specs_dir  = root / ".harness" / "specs"
    return f"""{_HARNESS_BLOCK_START}
## Harness

For every task in this project — call `harness_ticket_context` first (MCP), or
run `harness rag-pack "<task>"` if MCP is unavailable.  Never `grep`/`find`/`read_file`
source files before loading Harness context.

- Project root : `{root}`
- Rules + tools: `{harness_md}` (mandatory first-step rule, Tier-1 MCP table)
- Full docs    : `{root}/HARNESS.html` (architecture, modules, conventions, tickets)

**Workflow tasks** (`harness workflow`): when you receive a prompt that starts with
`== HARNESS WORKFLOW TASK ==`, check `{specs_dir}` for the matching spec HTML file,
read it fully before touching any source file, then follow the Implementation Plan
step by step.  Record key decisions with `harness_record_memory` after completing.
{_HARNESS_BLOCK_END}"""


def inject_agent_instructions(root: Path, harness_root: Path | None = None) -> list[str]:
    """Inject a compact harness reference block into agent instruction files.

    Checks CLAUDE.md, AGENTS.md, CODEX.md, GEMINI.md.  Only injects into files
    that already exist (don't create new ones — the user manages those).  If a file
    has no harness block yet, appends one.  If it already has one, replaces it.

    Returns list of filenames that were written or updated.
    """
    block   = _harness_instruction_block(root, harness_root)
    updated = []

    for filename in _AGENT_INSTRUCTION_FILES:
        path = root / filename
        if not path.exists():
            continue   # skip — only inject into files the user already maintains
        try:
            content = path.read_text(encoding="utf-8")
            if _HARNESS_BLOCK_START in content:
                start = content.index(_HARNESS_BLOCK_START)
                end   = content.index(_HARNESS_BLOCK_END) + len(_HARNESS_BLOCK_END)
                new_content = content[:start] + block + content[end:]
            else:
                new_content = content.rstrip("\n") + "\n\n" + block + "\n"
            path.write_text(new_content, encoding="utf-8")
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


def is_initialized(target_root: Path) -> bool:
    """Return True if the project has already been initialized (state.json exists)."""
    return (target_root / ".harness" / "state.json").exists()


def init_project_full(
    target_root: Path,
    harness_root: Path,
    analysis: dict[str, Any],
    *,
    dry_run: bool = False,
    skip_index: bool = False,
    force: bool = False,
    agent_sections: "dict[str, Any] | None" = None,
) -> dict[str, Any]:
    """Initialize or re-initialize a project.

    On first run (force=False, no .harness/):  full init — creates everything.
    On re-run   (force=False, .harness/ exists): skips expensive data files
        (index, memory, features, state, hooks, growth) that already exist.
        Always refreshes docs, MCP schema, agent injection, MCP registration.
    force=True: rebuilds everything regardless.
    """
    created: list[str] = []
    skipped: list[str] = []

    hd = target_root / ".harness"

    def _should_skip(path: Path) -> bool:
        """Return True when the path exists and we are not forcing a rebuild."""
        return (not force) and path.exists()

    def _write(path: Path, text: str, *, always: bool = False) -> None:
        """Write file. always=True bypasses skip logic (used for cheap re-gen)."""
        if _should_skip(path) and not always:
            skipped.append(str(path))
            return
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        created.append(str(path))

    def _mkdir(path: Path) -> None:
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)

    # ── core config ────────────────────────────────────────────────────────────
    state_path = hd / "state.json"
    if not _should_skip(state_path):
        state = default_state()
        state["routing_policy"].update(analysis.get("routing_keywords", {}))
        if not dry_run:
            save_state(state_path, state)
        created.append(str(state_path))
    else:
        skipped.append(str(state_path))

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
    # project.json always updated — cheap and keeps metadata current
    _write(hd / "project.json",
           json.dumps(project_meta, indent=2, ensure_ascii=False) + "\n",
           always=True)

    # ── BM25 index — skip if already built ───────────────────────────────────
    index_path = hd / "index.json"
    if _should_skip(index_path) or skip_index:
        skipped.append(str(index_path))
    else:
        if not dry_run:
            build_index(target_root, index_path)
        created.append(str(index_path))

    # ── memory — skip if exists (preserves accumulated memories) ─────────────
    memory_path = hd / "memory.jsonl"
    if not _should_skip(memory_path):
        if not dry_run:
            seed_memories(memory_path, analysis.get("initial_memories", []))
        created.append(str(memory_path))
    else:
        skipped.append(str(memory_path))

    # ── artifact subdirs — always create (idempotent) ─────────────────────────
    for subdir in ("handoffs", "context_packs", "evaluations"):
        _mkdir(hd / subdir)

    handoff_readme = hd / "handoffs" / "README.md"
    if not handoff_readme.exists():
        _write(handoff_readme, "# Handoffs\n\nWrite compact center-to-center handoffs here.\n")

    # ── feature list — skip if exists ────────────────────────────────────────
    feature_path = hd / "feature_list.json"
    if not _should_skip(feature_path):
        if not dry_run:
            init_feature_list(feature_path, analysis.get("initial_features", []))
        created.append(str(feature_path))
    else:
        skipped.append(str(feature_path))

    # ── MCP config — always update (idempotent) ───────────────────────────────
    mcp_config = generate_mcp_config(harness_root, target_root)
    _write(hd / "mcp.json",
           json.dumps(mcp_config, indent=2, ensure_ascii=False) + "\n",
           always=True)

    # ── lifecycle hooks — skip if user has customized ─────────────────────────
    hooks_path = target_root / ".harness" / "hooks.json"
    if not _should_skip(hooks_path):
        if not dry_run:
            save_hooks(target_root, default_hooks())
        created.append(str(hooks_path))
    else:
        skipped.append(str(hooks_path))

    # ── per-project self-growth bootstrap — skip if started ──────────────────
    growth_dir = target_root / ".harness" / "growth"
    if not _should_skip(growth_dir):
        if not dry_run:
            bootstrap_growth(target_root, analysis.get("initial_features", []))
        created.append(str(growth_dir))
    else:
        skipped.append(str(growth_dir))

    # ── docs — always regenerate (cheap, no data loss) ────────────────────────
    project_name = analysis.get("project_name", target_root.name)
    _write(target_root / "HARNESS.md",
           render_harness_md(analysis, harness_root / "scripts", project_name),
           always=True)

    # ── MCP schema doc — always regenerate ───────────────────────────────────
    if not dry_run:
        from harness_core.mcp_schema import write_mcp_schema
        schema_path = write_mcp_schema(target_root, harness_root)
        created.append(str(schema_path))
    else:
        created.append(str(target_root / ".harness" / "mcp_schema.md"))

    # ── generate AGENTS.md / CODEX.md via LLM if missing ────────────────────
    if not dry_run:
        for fname in ("AGENTS.md", "CODEX.md"):
            p = target_root / fname
            if not p.exists():
                content = generate_agents_md(analysis, target_root)
                p.write_text(content + "\n", encoding="utf-8")
                created.append(str(p))

    # ── inject harness block into agent instruction files — always ────────────
    if not dry_run:
        inject_agent_instructions(target_root, harness_root)

    # ── register MCP server — always (idempotent) ────────────────────────────
    if not dry_run:
        from harness_core.mcp_registration import register_mcp_project, register_mcp_global
        mcp_written = register_mcp_project(target_root, harness_root)
        mcp_written += register_mcp_global(harness_root)
        for p in mcp_written:
            created.append(p)

    # ── save agent research if provided ──────────────────────────────────────
    if agent_sections and not dry_run:
        from harness_core.agent_research import save_research
        save_research(target_root, agent_sections)

    # ── load existing research + workflow for HARNESS.html ───────────────────
    from harness_core.workflow_steps import load_workflow
    workflow = load_workflow(target_root)
    if agent_sections is None:
        from harness_core.agent_research import load_research
        agent_sections = load_research(target_root)

    _write(target_root / "HARNESS.html",
           render_harness_html(analysis, project_name, harness_root / "scripts",
                               agent_sections=agent_sections, workflow=workflow),
           always=True)

    return {
        "root":        str(target_root),
        "harness_dir": str(hd),
        "dry_run":     dry_run,
        "force":       force,
        "analysis":    {k: v for k, v in analysis.items() if k != "initial_memories"},
        "created":     created,
        "skipped":     skipped,
    }


# ── Data preserved by refresh (never overwritten) ─────────────────────────────
_PRESERVE = {
    ".harness/memory.jsonl",
    ".harness/index.json",
    ".harness/workflow.json",
    ".harness/agent_research.json",
    ".harness/feature_list.json",
    ".harness/hooks.json",
    ".harness/context_packs",   # directory
    ".harness/indexes",         # directory
    ".harness/trajectories",    # directory
    ".harness/telemetry",       # directory
    ".harness/growth",          # directory
}


def refresh_project_files(target_root: Path, harness_root: Path) -> dict[str, Any]:
    """Regenerate docs and MCP config after a harness upgrade.

    Rewrites:  HARNESS.md, HARNESS.html, .harness/mcp_schema.md,
               CLAUDE.md, AGENTS.md, GEMINI.md, .mcp.json, ~/.gemini/* configs
    Preserves: memory, index, context_packs, workflow, trajectories, growth, ...
    """
    hd = target_root / ".harness"
    refreshed: list[str] = []
    skipped:   list[str] = []

    # ── load existing project metadata ────────────────────────────────────────
    project_json = hd / "project.json"
    if not project_json.exists():
        raise FileNotFoundError(
            f".harness/project.json not found — run  harness init  first: {target_root}"
        )
    meta = json.loads(project_json.read_text(encoding="utf-8"))
    project_name = meta.get("project_name", target_root.name)

    # Re-run heuristic analysis (fast, no agent) to pick up language/framework changes
    analysis = analyze_project(target_root)
    # Preserve harness_root from original init in case project was moved
    meta["harness_root"] = str(harness_root)
    meta["analyzed_at"]  = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    project_json.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    refreshed.append(str(project_json))

    # ── regenerate MCP schema first (agent files embed Tier-1 table from it) ──
    from harness_core.mcp_schema import write_mcp_schema
    schema_path = write_mcp_schema(target_root, harness_root)
    refreshed.append(str(schema_path))

    # ── re-inject agent instruction files ────────────────────────────────────
    updated = inject_agent_instructions(target_root, harness_root)
    refreshed.extend(str(target_root / f) for f in updated)

    # ── re-register MCP in agent config files ────────────────────────────────
    from harness_core.mcp_registration import register_mcp_project, register_mcp_global
    mcp_written = register_mcp_project(target_root, harness_root)
    mcp_written += register_mcp_global(harness_root)
    refreshed.extend(mcp_written)

    # ── regenerate HARNESS.md ─────────────────────────────────────────────────
    harness_md = target_root / "HARNESS.md"
    harness_md.write_text(
        render_harness_md(analysis, harness_root / "scripts", project_name),
        encoding="utf-8",
    )
    refreshed.append(str(harness_md))

    # ── load preserved workflow + agent research for HARNESS.html ─────────────
    from harness_core.workflow_steps import load_workflow
    from harness_core.agent_research import load_research
    workflow       = load_workflow(target_root)
    agent_sections = load_research(target_root)

    # ── regenerate HARNESS.html ───────────────────────────────────────────────
    harness_html = target_root / "HARNESS.html"
    harness_html.write_text(
        render_harness_html(
            analysis, project_name, harness_root / "scripts",
            agent_sections=agent_sections, workflow=workflow,
        ),
        encoding="utf-8",
    )
    refreshed.append(str(harness_html))

    # report what was intentionally left alone
    for rel in sorted(_PRESERVE):
        p = target_root / rel
        if p.exists():
            skipped.append(rel)

    return {
        "root":      str(target_root),
        "refreshed": refreshed,
        "preserved": skipped,
    }
