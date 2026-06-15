# Context Economy Rules

The default mode is token conservation.

Before sending cloud context:

1. benchmark raw vs compact context when the task is repo-wide
2. prefer file paths, symbols, and line references over full files
3. use context packs under `production_artifacts/context_packs/`
4. keep handoffs short and evidence-based
5. compact repeated tool/log output with `scripts/harness-compact-output`
6. retrieve a bounded memory pack instead of replaying old conversations

Use:

```bash
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-benchmark <repo> "<query>"
/Users/danchoingoinhinmuaroi/Projects/Harness/scripts/harness-contextual <repo> "<query>" 5
```

Prefer contextual packs for codebase handoffs because each snippet carries path, query, nearest symbol or heading, and a local relevance score. This keeps downstream Codex/Claude/Antigravity prompts compact without stripping away orientation.

For code queries with multiple likely files or large source files, prefer `scripts/harness-hybrid-context`. It ranks line chunks, boosts path/symbol matches, and selects distinct files before duplicate chunks.

Use semantic embeddings only through `scripts/harness-semantic-index plan` first. Reuse cached vectors for unchanged chunks, and accept the hybrid lexical fallback whenever the live local-model gate blocks Ollama.

Target savings:

- under 25%: context pack is too broad; refine query or chunking
- 25-50%: acceptable for coding tasks
- 50-75%: good default target
- over 75%: good for research/log-heavy tasks, but verify no key evidence was lost

Character-based benchmarks are directional only. For evidence-grade savings claims, record paired baseline and harness runs with the same task fingerprint and center using `scripts/harness-experiment`; reject pairs with failed runs or quality regression.

Do not publish a tri-center savings claim until `scripts/harness-health` reports token evidence for Codex, Claude, and Antigravity. Missing pairs and non-positive savings remain explicit constraints.

When `scripts/harness-autopilot` returns `run_token_experiment`, that queued measurement takes priority over optional new capability work.
