# Harness

**Agent-driven project onboarding and continuous work-loop tooling for Claude Code, Codex, Antigravity, and local Ollama models.**

Harness does two things:
1. **Init** — one command analyzes your project, picks an agent, and generates a living `HARNESS.html` doc with architecture, conventions, ticket workflow, and open questions, all derived from your actual codebase and git history.
2. **Work loop** — every subsequent session starts from that doc instead of re-scanning the repo from scratch, cutting context tokens by 50–75%.

---

## Install

**macOS / Linux**
```bash
git clone https://github.com/huynhthaitu124/harness ~/Projects/Harness
cd ~/Projects/Harness
./install.sh          # creates ~/.local/bin/harness symlink, updates ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/huynhthaitu124/harness $env:USERPROFILE\Projects\Harness
cd $env:USERPROFILE\Projects\Harness
.\install.ps1         # adds scripts\ to user PATH — no admin required
# restart terminal
```

**Windows (Git Bash)**
```bash
./install.sh          # delegates to PowerShell automatically
```

**Requirements:** Python 3.10+, git. Node/npm only needed if you install Claude Code or Codex CLI. Ollama optional for local inference.

---

## Commands at a glance

Run `harness` with no arguments inside any project to open the interactive menu.

| Command | What it does |
|---|---|
| `harness init` | Full project init: detect stack → pick agent → deep research → write `HARNESS.html` + `HARNESS.md` |
| `harness grill` | Q&A session that fills the `[CUSTOMIZE]` section in `HARNESS.md` |
| `harness status` | Show routing center, memory count, feature progress |
| `harness analyze` | Print project profile JSON — language, framework, entry points |
| `harness center set <center>` | Set preferred center for this project (`auto` / `codex` / `claude` / `antigravity`) |
| `harness center get` | Show the current center |
| `harness rag-pack "<task>"` | Build a shared RAG context pack for all centers |
| `harness index` | Build / rebuild the local BM25 + semantic RAG index |
| `harness eject` | Remove harness config from the project, keep `production_artifacts/` data |

---

## Phase 1 — Init

Run once per project. Harness walks you through agent selection, deep-researches your codebase, and writes everything into `HARNESS.html`.

```bash
cd ~/Projects/my-app
harness init
```

### Step 1 — Pick an agent

Harness detects what is installed and shows availability:

```
  ✓  Claude Code     /usr/local/bin/claude
  ✓  Local — qwen3:8b  offline · no API cost
  !  Codex           installed — set OPENAI_API_KEY
  ↓  Local model (Ollama — no models pulled yet)
```

If an agent is not installed, Harness offers to install it. If it needs authentication (Claude Code opens the browser for you), Harness handles the auth flow before continuing.

### Step 2 — Architecture research

The selected agent reads your key files — `README`, config files, entry points, agent configs — and generates project-specific sections for `HARNESS.html`:

- Architecture overview and tech stack
- Key modules with file paths and when to edit them
- Coding conventions and patterns
- Build & test commands
- Open questions and tech debt

All sections are rendered as a navigable visual doc at `HARNESS.html`. Open it in any browser.

### Step 3 — Workflow inference

The same agent reads your git log, all branches, and CI config files to infer your ticket workflow automatically:

```
✓  Workflow inferred from git history:
   ticket_system    openproject
   base_branch      development
   branch_pattern   bug/<id>
   build_cmd        msbuild PAGSWebRole
   critical_rules   Never commit directly to development
```

You are then offered three options:

```
  1  Accept as-is
  2  Review & edit each field   (pre-filled — press Enter to keep, type to override)
  3  Describe in your own words → agent parses
  0  Skip
```

The workflow is saved to `.harness/workflow.json` and rendered as the **Ticket Workflow** section in `HARNESS.html`, visible to every agent that reads the file.

### What gets created

```
.harness/
  state.json          routing policy and preferred center
  project.json        detected language, framework, entry points
  index.json          BM25 search index
  memory.jsonl        seeded architecture memories
  mcp.json            MCP server config pointing at this project
  workflow.json       ticket workflow (ticket system, branch pattern, build cmd, rules)
  agent_research.json raw agent-generated sections

HARNESS.md            agent-readable guidelines + project profile
HARNESS.html          full visual doc: architecture, modules, conventions, workflow, open questions
```

---

## Phase 2 — Work loop

Every session after init, agents start from `HARNESS.html` instead of exploring the repo cold.

### Starting a session

Open `HARNESS.html` in your browser before starting any ticket. The doc contains everything an agent needs: architecture, which files to edit, how to branch, what to build, and critical rules.

Add this line to your `AGENTS.md` or `CLAUDE.md`:

```
Read HARNESS.html before starting any work on this project.
```

If it is not there, `harness init` writes it into `HARNESS.md` automatically.

### Building context for a task

Instead of passing raw file dumps to an agent, build a compact context pack:

```bash
harness rag-pack "fix login token handling"
# writes .harness/context_packs/last-rag-pack.md
# prints copy-ready commands for claude, codex, and local ollama
```

For more targeted retrieval:

```bash
# BM25 + path/symbol boost — best for code navigation
harness-hybrid-context . "auth token refresh" 5

# Contextual snippets annotated with path, symbol, and local relevance
harness-contextual . "auth token refresh" 5
```

### Routing a task to the right center

```bash
harness-route "research the auth flow before editing"
```

In `auto` mode, routing reads task affinity, the shared usage ledger, and live center readiness. An explicitly selected center overrides auto while it is available.

Check live readiness before a long delegation:

```bash
harness-readiness
```

### Switching center mid-session

```bash
harness center set codex        # heavy refactors, repo-wide changes
harness center set claude       # compact review, quick fixes
harness center set antigravity  # broad research, large context budget
harness center set auto         # router decides per task
```

### Recording a handoff

When switching centers, write a compact handoff so the receiving agent has full context:

```bash
harness-handoff record --title "auth refactor" --from claude --to codex
# writes .harness/handoffs/<timestamp>.json
```

Validate the manifest before the other agent picks it up:

```bash
harness-handoff validate .harness/handoffs/<handoff>.json
```

### Memory

```bash
harness-memory search . "quota local model routing"   # ranked search
harness-memory pack   . "quota local model routing"   # build a memory context pack
harness-memory sync   . production_artifacts/memory.jsonl
```

Memories are deduplicated by content hash, ranked by relevance and recency, and synced from handoff and growth-cycle artifacts.

---

## Diagnostics

### Doctor

```bash
harness-health        # aggregate: tests, MCP, retrieval quality, research freshness, center readiness
```

### MCP server

```bash
python3 -m harness_mcp.server   # used by Claude Code and Codex directly
harness-mcp-check               # protocol-level conformance after any MCP change
harness-mcp-security            # audit for unsafe shell execution patterns
```

### Context pack audit

```bash
harness-context-pack-audit      # check size budget, provenance, and code-fenced evidence
```

Run this before sending a RAG handoff to a cloud center.

### Token benchmarking

```bash
harness-benchmark . "auth flow debug"   # raw text tokens vs compact context pack
```

---

## Why Harness

### Token savings

Every agent session normally starts by exploring the repo: reading `README`, opening config files, tracing entry points. On a mid-size project that costs 10,000–30,000 input tokens before a single line of code is written.

With Harness, `HARNESS.html` front-loads all of that into a single pre-built document. The agent reads one file instead of twenty. Measured on real sessions: **50–75% fewer input tokens per task**.

The RAG context pack narrows it further — instead of passing entire files, you pass the three most relevant chunks for the current task.

### Claude Code — what you get without Codex or Antigravity

Harness is fully useful with Claude Code alone:

| Without Harness | With Harness |
|---|---|
| Claude re-explores the repo every session | `HARNESS.html` loaded once, referenced every session |
| Ticket context must be explained each time | Ticket workflow baked into `HARNESS.html` — branch pattern, build cmd, critical rules |
| Architecture lives in your head | Architecture section in `HARNESS.html` — auto-generated by Claude itself during init |
| No shared memory across sessions | `.harness/memory.jsonl` — seeded at init, grows over time |
| Raw file dumps in context | RAG pack: 3 relevant chunks instead of 3 full files |

You run `harness init` once. Claude writes its own onboarding doc. Every future session costs less and starts faster.

### The work loop in practice

```
Ticket assigned
  → read HARNESS.html (architecture + ticket workflow already there)
  → harness rag-pack "fix the thing"   (3 relevant chunks, not 30 files)
  → agent implements, builds, hands off
  → .harness/memory.jsonl updated

Next ticket starts from memory, not from scratch.
```

The doc improves over time. Each `harness grill` session adds more project-specific context. Each handoff adds to memory. The longer you use it on a project, the cheaper each session gets.
