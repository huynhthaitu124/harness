---
name: harness-router
description: Use before repo-wide, debug, research, refactor, or multi-agent work to reduce token usage through the shared tri-center harness.
---

# Harness Router

Before doing read-heavy work, use the shared harness in `/Users/danchoingoinhinmuaroi/Projects/Harness`.

Run:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-route "<task>"
```

Follow the returned center and workflow:

- If `rag_summarize` is present, create or request a compact context pack before asking a cloud model to reason.
- If another center should lead, write a short handoff under `production_artifacts/handoffs/`.
- Avoid raw repository dumps. Pass file paths, symbols, and concise evidence packs.
- Completion is default-fail until tests or concrete evidence exist.
- If autopilot returns `run_token_experiment`, run only the queued baseline or harness task and record measured usage; do not improvise a different prompt.

For long-running projects, initialize the filesystem harness:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-init-project <repo> "Feature one" "Feature two"
```

For token checks:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-benchmark <repo> "<query>"
```

Before delegation, check current center and local-worker health:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-readiness
```

For compact code retrieval and noisy tool output:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness rag-pack "<task>" <repo>
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-hybrid-context <repo> "<query>" 5
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-compact-output <log-file> 4000
```

`harness rag-pack` writes `.harness/context_packs/last-rag-pack.md` and includes ready commands for Codex, Claude Sonnet, Antigravity, and local Ollama. Use that shared pack instead of rescanning the repository.

For evidence-grade token savings and center changes:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-experiment report <experiments.jsonl>
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-handoff validate <handoff.json>
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-autopilot plan
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-campaign status
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-local-pipeline <chunk-count> "<task>"
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-memory pack <memory.jsonl> "<query>"
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-command-policy "<command>"
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-mcp-check
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-mcp-security
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-context-pack-audit
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-codex-preflight "<task>" --local
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-health
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-experiment-queue next
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-experiment-queue prepare
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-experiment-quality <output.json>
```

Antigravity is quality/success checked; do not block workflow on token usage extraction from `agy`.

For local search before cloud reasoning:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-index build <repo> <index.json>
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-index search <index.json> "<query>"
```

The user may switch preferred center with:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-center set auto
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-center set codex
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-center set claude
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-center set antigravity
```
