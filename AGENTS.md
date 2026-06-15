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

Before any read-heavy, repo-wide, debug, research, refactor, or multi-agent task, call the shared harness router first:

1. Use `harness_route_task` with the user's task.
2. If it says `rag_summarize`, get or create a compact context pack before asking any cloud center to reason.
3. Delegate only the compact context pack, never raw repo dumps.
4. Record a handoff when switching center.

For long-running work, initialize or use `feature_list.json`. Features are default-fail and require evidence before completion.

## Core Workflow Commands

- `scripts/harness`: unified project CLI — run from inside a project directory. Subcommands: `init`, `eject`, `analyze`, `grill`, `status`. Accepts an optional path argument to target a different directory.
- `scripts/harness-init`: low-level init entry point (used internally by `harness init`).
- `scripts/harness-analyze-project`: low-level analyze entry point (used internally by `harness analyze`).
- `scripts/harness-grill-project`: low-level grill entry point (used internally by `harness grill`).
- `scripts/harness-eject`: low-level eject entry point (used internally by `harness eject`).
- `scripts/harness-route`: select the center and workflow.
- `scripts/harness-readiness`: verify live CLI, quota, failure, and local-worker state before delegation.
- `scripts/harness-hybrid-context`: build the default compact code context pack.
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
- `scripts/harness-context-pack-audit`: audit context packs for token budget and provenance before cloud handoff.
- `scripts/harness-codex-preflight`: build the compact Memory/RAG/local-Qwen payload before Codex reads repo-heavy context.
- `scripts/harness-health`: aggregate tests, doctor, MCP, retrieval, research, readiness, and campaign evidence.
- `scripts/harness-experiment-queue`: plan, blueprint, or prepare the next reproducible baseline/harness token run when a center is ready.
- `scripts/harness-experiment-quality`: score structured run quality before recording token savings.

## Token Policy

Default to the cheapest reliable path:

- Use local/file/RAG summarization before cloud reasoning.
- Before Codex executes repo-heavy work, run `scripts/harness-codex-preflight "<task>" --local` when Qwen is usable; send the compact payload, not raw repo context.
- Keep tool outputs short and cite paths/line numbers instead of pasting whole files.
- Use one center at a time unless there is a clear evaluation benefit.
- Use fresh-context evaluation for final review, but only after a compact evidence pack exists.

## Validation

Completion is default-fail. Do not mark work complete until there is evidence:

- tests, lint, typecheck, or a clear reason they are unavailable
- relevant file references
- a concise handoff in `production_artifacts/handoffs/` for long tasks
