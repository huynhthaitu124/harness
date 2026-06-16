# Tri-Center Harness Rules

This repository defines the shared harness for Codex, Claude Code, and Antigravity.

Read the rule files in `rules/` when relevant:

- `rules/00-center-selection.md`
- `rules/10-context-economy.md`
- `rules/20-anthropic-harness-parity.md`
- `rules/30-shared-tooling.md`

## Center Selection

The user may switch the active center at any time:

- `codex`: best for deep repo control, Codex plugins, browser/computer use, and OpenAI-first workflows.
- `claude`: best when Codex quota is low, for code implementation/review after context is compressed.
- `antigravity`: best when large token budget or Gemini/Antigravity tooling is preferred.
- `auto`: ask the harness router to choose.

Use the smallest Harness mode that helps:

- `fast`: exact file/function or tiny edit. Work directly after reading the named file.
- `light`: target unclear but task is small. Use `harness locate "<task>"` or MCP `harness_locate_context`, then read the real files it suggests.
- `deep`: read-heavy, repo-wide, debug, research, refactor, token/RAG/memory, handoff, or multi-agent task. Use `harness_route_task` or `harness_ticket_context`, then build a compact context pack if needed.

RAG packs are navigation aids, not source of truth. Before editing, read actual target files and relevant tests. Extra `rg`/read calls are expected when they answer a specific locator verification question.

For long-running work, initialize or use `feature_list.json`. Features are default-fail and require evidence before completion.

## Core Workflow Commands

- `scripts/harness`: unified project CLI — run from inside a project directory. Subcommands: `init`, `eject`, `analyze`, `grill`, `status`, `center`, `locate`, `rag-pack`, `local`, `readiness`, `usage`, `mcp`. Accepts an optional path argument to target a different directory.
- `scripts/harness-init`: low-level init entry point (used internally by `harness init`).
- `scripts/harness-analyze-project`: low-level analyze entry point (used internally by `harness analyze`).
- `scripts/harness-grill-project`: low-level grill entry point (used internally by `harness grill`).
- `scripts/harness-eject`: low-level eject entry point (used internally by `harness eject`).
- `scripts/harness-route`: select the center and workflow.
- `scripts/harness-readiness`: verify live CLI, quota, failure, and local-worker state before delegation.
- `harness readiness`: unified live readiness report for Codex, Claude, Antigravity, and local Ollama.
- `scripts/harness-hybrid-context`: build the default compact code context pack.
- `harness locate "<task>"`: fast locator with likely files, symbols, tests, exact reads, and verification questions.
- `harness rag-pack "<task>"`: write `.harness/context_packs/last-rag-pack.md` with one shared RAG payload plus Codex, Claude Sonnet, Antigravity, and local Ollama commands.
- `harness local plan "<task>"`: plan embedding model, structured local worker, and fallback RAG path before using Ollama for complex work.
- `harness research-refresh`: refresh the default official Codex, Claude, Ollama, MCP, and Antigravity source registry.
- `harness usage ingest-claude|ingest-codex <raw-output-file>`: record measured cloud token usage into the shared ledger.
- `scripts/harness-compact-output`: shrink noisy logs/tool output before cloud handoff.
- `scripts/harness-experiment`: record paired baseline/harness token evidence.
- `scripts/harness-handoff`: validate structured handoff manifests when changing centers.
- `scripts/harness-autopilot`: select the next bounded self-growth action from current evidence.
- Autopilot prioritizes a ready token experiment queue before new feature exploration once integrity, retrieval, and research gates pass.
- `scripts/harness-campaign`: audit duration, cycle count, and provider source coverage.
- `scripts/harness-local-pipeline`: plan complex local map-reduce-verify work behind the live memory gate.
- `scripts/harness-memory`: retrieve bounded source-cited operational and decision memory.
- `scripts/harness-command-policy`: enforce ALLOW/REVIEW/DENY before autonomous shell execution.
- `scripts/harness-mcp-check`: run protocol-level MCP conformance after server changes.
- `scripts/harness-mcp-security`: audit MCP process-execution posture and command-policy coverage.
- `harness mcp security`: run the unified MCP security audit from the project CLI.
- `scripts/harness-context-pack-audit`: audit context packs for token budget and provenance before cloud handoff.
- `scripts/harness-codex-preflight`: build the compact Memory/RAG/local-Qwen payload before Codex reads repo-heavy context.
- `scripts/harness-health`: aggregate tests, doctor, MCP, retrieval, research, readiness, and campaign evidence.
- `scripts/harness-experiment-queue`: plan, blueprint, or prepare the next reproducible baseline/harness token run when a center is ready.
- `scripts/harness-experiment-quality`: score structured run quality before recording token savings.

## Token Policy

Default to the cheapest reliable path:

- Use local/file/RAG summarization before cloud reasoning.
- Before any cloud center scans broad repo context, prefer `harness locate "<task>"` first; escalate to `harness rag-pack "<task>"` only when locator is insufficient or handoff/deep reasoning is needed.
- Before Codex executes repo-heavy work, run `scripts/harness-codex-preflight "<task>" --local` when Qwen is usable; send the compact payload, not raw repo context.
- Keep tool outputs short and cite paths/line numbers instead of pasting whole files.
- Use one center at a time unless there is a clear evaluation benefit.
- Use fresh-context evaluation for final review, but only after a compact evidence pack exists.

## Validation

Completion is default-fail. Do not mark work complete until there is evidence:

- tests, lint, typecheck, or a clear reason they are unavailable
- relevant file references
- a concise handoff in `production_artifacts/handoffs/` for long tasks
