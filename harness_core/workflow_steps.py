"""Per-project ticket workflow definition.

Stores a project's actual work loop in .harness/workflow.json so every agent
session starts with the same playbook — regardless of which AI tool is used.

Each project fills this once (via harness grill) and the data is rendered into
HARNESS.md and HARNESS.html for agents to read before picking up any ticket.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_WORKFLOW_FILE = ".harness/workflow.json"


# ── Grill questions for workflow setup ────────────────────────────────────────

WORKFLOW_GRILL_QUESTIONS: list[dict[str, str]] = [
    {
        "key": "wf_ticket_system",
        "q":   "Ticket system? (openproject / jira / linear / github / notion / none)",
    },
    {
        "key": "wf_ticket_url",
        "q":   "Ticket base URL or project key? (e.g. https://op.bigin.vn  or  PROJ-)",
    },
    {
        "key": "wf_base_branch",
        "q":   "Working base branch? (e.g. development, main, master)",
    },
    {
        "key": "wf_branch_pattern",
        "q":   "Branch naming pattern? (e.g. bug/<id>  feat/<id>  fix/<id>-<slug>)",
    },
    {
        "key": "wf_context_files",
        "q":   "Files/docs to load before every ticket? (comma-sep, e.g. AGENTS.md, docs/arch.md)",
    },
    {
        "key": "wf_build_cmd",
        "q":   "Build/test verification command? (run after every change, e.g. npm test  dotnet build  msbuild PAGSWebRole)",
    },
    {
        "key": "wf_critical_rules",
        "q":   "Critical rules agents MUST always follow? (one per line — use \\n between, or just the most important one)",
    },
]


# ── Schema ────────────────────────────────────────────────────────────────────

def empty_workflow() -> dict[str, Any]:
    return {
        "ticket_system":   "",
        "ticket_url":      "",
        "base_branch":     "main",
        "branch_pattern":  "feat/<id> | bug/<id>",
        "context_files":   [],
        "build_cmd":       "",
        "critical_rules":  [],
        "steps":           _default_steps(),
    }


def _default_steps() -> list[dict[str, str]]:
    return [
        {
            "id":     "01-context",
            "title":  "Load project context",
            "detail": "Read HARNESS.html + HARNESS.md. Then fetch RAG context BEFORE reading source files: call harness_contextual_context_pack(query=<task>) via MCP, or run `harness rag-pack \"<task>\" --ticket <id>` via CLI.",
        },
        {
            "id":     "02-ticket",
            "title":  "Fetch full ticket",
            "detail": "Get requirements, acceptance criteria, and comments (QA feedback is in comments).",
        },
        {
            "id":     "03-branch",
            "title":  "Create working branch",
            "detail": "Checkout base branch → pull → create branch following the project's naming pattern.",
        },
        {
            "id":     "04-explore",
            "title":  "Explore relevant code",
            "detail": "Grep/glob only the files that need changing. Read them before editing.",
        },
        {
            "id":     "05-scope",
            "title":  "Assess scope",
            "detail": "Small (1-3 files, no new schema, existing actions) → implement directly. Large → write plan, get approval, then implement.",
        },
        {
            "id":     "06-implement",
            "title":  "Implement",
            "detail": "Follow project conventions. Apply critical rules. Invoke any required sub-skills.",
        },
        {
            "id":     "07-verify",
            "title":  "Verify build / tests",
            "detail": "Run the project's build_cmd. Fix all errors before reporting done.",
        },
        {
            "id":     "08-handoff",
            "title":  "Hand off",
            "detail": "List modified files, summarise changes, report build result, flag any follow-on tasks.",
        },
        {
            "id":     "09-record",
            "title":  "Record outcome",
            "detail": "Update changelog / memory with ticket ID, files changed, and key decisions.",
        },
    ]


# ── Grill answer → workflow ───────────────────────────────────────────────────

def answers_to_workflow(grill_answers: dict[str, str]) -> dict[str, Any]:
    """Convert raw grill answers (wf_* keys) into a workflow dict."""
    wf = empty_workflow()

    if ts := grill_answers.get("wf_ticket_system", "").strip():
        wf["ticket_system"] = ts.lower()
    if url := grill_answers.get("wf_ticket_url", "").strip():
        wf["ticket_url"] = url
    if bb := grill_answers.get("wf_base_branch", "").strip():
        wf["base_branch"] = bb
    if bp := grill_answers.get("wf_branch_pattern", "").strip():
        wf["branch_pattern"] = bp
    if cf := grill_answers.get("wf_context_files", "").strip():
        wf["context_files"] = [f.strip() for f in cf.replace(";", ",").split(",") if f.strip()]
    if bc := grill_answers.get("wf_build_cmd", "").strip():
        wf["build_cmd"] = bc
    if cr := grill_answers.get("wf_critical_rules", "").strip():
        wf["critical_rules"] = [r.strip() for r in cr.split("\\n") if r.strip()]

    # Patch default steps with project-specific detail
    for step in wf["steps"]:
        if step["id"] == "01-context" and wf["context_files"]:
            files = ", ".join(wf["context_files"][:4])
            step["detail"] = (
                f"Read HARNESS.html + HARNESS.md. Also load: {files}. "
                f"Then call harness_contextual_context_pack(query=<task>) or run "
                f"`harness rag-pack \"<task>\" --ticket <id>` BEFORE reading source files."
            )
        if step["id"] == "02-ticket" and wf["ticket_system"]:
            step["detail"] = (
                f"Fetch from {wf['ticket_system']} ({wf['ticket_url'] or 'see project config'}). "
                "Pull requirements AND comments — QA feedback lives in comments."
            )
        if step["id"] == "03-branch" and wf["base_branch"]:
            step["detail"] = (
                f"git checkout {wf['base_branch']} && git pull && "
                f"git checkout -b <branch>  (pattern: {wf['branch_pattern']})"
            )
        if step["id"] == "07-verify" and wf["build_cmd"]:
            step["detail"] = (
                f"Run: `{wf['build_cmd']}`. "
                "Fix all errors before handing off — never skip verification."
            )

    return wf


# ── Persistence ───────────────────────────────────────────────────────────────

def save_workflow(root: Path, wf: dict[str, Any]) -> Path:
    path = root / _WORKFLOW_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_workflow(root: Path) -> dict[str, Any] | None:
    path = root / _WORKFLOW_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── Render helpers (used by render_harness_md / render_harness_html) ──────────

def render_workflow_md(wf: dict[str, Any]) -> str:
    """Return a HARNESS.md Ticket Workflow section from a workflow dict."""
    lines = ["## Ticket Workflow\n"]

    system = wf.get("ticket_system", "")
    url    = wf.get("ticket_url", "")
    branch = wf.get("branch_pattern", "")
    base   = wf.get("base_branch", "")
    build  = wf.get("build_cmd", "")
    files  = wf.get("context_files", [])
    rules  = wf.get("critical_rules", [])
    steps  = wf.get("steps", [])

    if system or url:
        lines.append(f"**Ticket system:** {system}  {('— ' + url) if url else ''}\n")
    if branch:
        lines.append(f"**Branch pattern:** `{branch}` from `{base or 'main'}`\n")
    if build:
        lines.append(f"**Verification:** `{build}`\n")
    if files:
        lines.append(f"**Load before every ticket:** {', '.join(f'`{f}`' for f in files)}\n")

    if steps:
        lines.append("")
        for s in steps:
            lines.append(f"**{s['id']}  {s['title']}** — {s['detail']}\n")

    if rules:
        lines.append("\n### Critical rules\n")
        for r in rules:
            lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines)
