# Center Selection Rules

Use fast/light/deep before choosing a center:

- `fast`: exact file/function or tiny edit. Stay with the current agent and work directly.
- `light`: target unclear but task is small. Use `harness locate "<task>"` or MCP `harness_locate_context`, then read the real files it points to.
- `deep`: repo-wide, debugging, refactor, research, handoff, token/RAG/memory, or multi-agent work. Use `scripts/harness-center status` or MCP `harness_get_status`, then build a compact context pack if needed.

Use `scripts/harness-readiness` before long delegations or when a center recently failed.

Center meanings:

- `auto`: router chooses based on task shape and available quota.
- `codex`: use when Codex plugins, browser, computer-use, OpenAI docs, GitHub/Linear connectors, or local repo edits are central.
- `claude`: use when Codex quota is low or when a compact context pack is ready for implementation/review.
- `antigravity`: use when the task is very broad, exploratory, or benefits from Antigravity/Gemini budget.

In `auto` mode, rank available centers using normalized observed token usage from `production_artifacts/usage.jsonl`, relative budget, optional `remaining_percent`, and task affinity. Explicit user selection remains the highest-priority override while that center is available.

Switch with:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-center set auto
```

When changing centers for a long task, create and validate a structured handoff manifest. Do not transfer raw repository dumps.
