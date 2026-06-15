# Tri-Center Harness

Shared token-saving harness for Codex, Claude Code, and Antigravity.

## Install (new machine — run once)

**macOS / Linux:**
```bash
git clone <this-repo> ~/Projects/Harness
cd ~/Projects/Harness
./install.sh          # creates ~/.local/bin/harness symlink, updates ~/.zshrc if needed
source ~/.zshrc
```

**Windows (PowerShell):**
```powershell
git clone <this-repo> $env:USERPROFILE\Projects\Harness
cd $env:USERPROFILE\Projects\Harness
.\install.ps1         # adds scripts\ to user PATH (no admin required)
# restart terminal
```

**Windows (Git Bash):**
```bash
./install.sh          # delegates to PowerShell automatically
```

## Project init (run from inside any project)

```bash
cd ~/Projects/my-app
harness init          # detect stack, write .harness/, HARNESS.md, HARNESS.html
harness grill         # fill [CUSTOMIZE] section interactively
harness status        # show current state
harness eject         # remove harness config, keep production_artifacts data
```

## Autopilot

```bash
./scripts/harness-autopilot plan
```

The planner combines doctor integrity, live readiness, research freshness, retrieval quality, the token experiment queue, and pending default-fail features. It selects one bounded next action and falls back to local deterministic maintenance when no cloud center is ready. Destructive actions are never authorized by the planner.

Before autonomous shell execution, validate the command:

```bash
./scripts/harness-command-policy "python3 -m unittest discover -s tests"
```

Known read/test commands may be `ALLOW`; installs and remote mutations require `REVIEW`; destructive and download-to-shell patterns are `DENY`.

Track long-running campaign duration and source coverage:

```bash
./scripts/harness-campaign status
```

Campaign wall-clock status is supporting evidence only. Goal completion must still verify active work time and every required capability.

Aggregate the completion gates into one bounded report:

```bash
./scripts/harness-health
```

The health report fails closed on tests, doctor, MCP conformance, and retrieval quality. Research freshness, center readiness, campaign progress, and missing or regressive tri-center token experiments are explicit constraints rather than hidden failures.

## Local Memory

```bash
./scripts/harness-memory search production_artifacts/memory.jsonl "quota local model routing"
./scripts/harness-memory pack production_artifacts/memory.jsonl "quota local model routing"
./scripts/harness-memory sync . production_artifacts/memory.jsonl
```

Memories are deduplicated by content hash and ranked by query relevance, importance, and recency. Sync deterministically extracts structured growth-cycle and handoff fields; it does not summarize raw transcripts. Send only bounded source-cited memory packs to cloud centers.

## Switch Center

```bash
./scripts/harness-center set auto
./scripts/harness-center set codex
./scripts/harness-center set claude
./scripts/harness-center set antigravity
```

Check live readiness before a long delegation:

```bash
./scripts/harness-readiness
```

The report combines CLI/MCP/plugin probes, quota reset hints, transient worker failures, and the live local-model memory gate.

## Codex Preflight

```bash
./scripts/harness-codex-preflight "fix tri-center routing and reduce Codex token usage" --local
```

Run this before Codex receives repo-heavy context. It builds a Memory/RAG payload, optionally distills it through local Qwen using Ollama `/api/chat` with `think:false`, writes `production_artifacts/context_packs/codex-preflight-context.md`, and reports estimated raw-vs-Codex token reduction. Claude worker runs should use Sonnet with tools available; Antigravity is quality/success checked rather than token-metered.

## Route A Task

```bash
./scripts/harness-route "research the auth flow before editing"
```

In `auto` mode, routing uses the shared usage ledger, each center's relative budget, optional `remaining_percent` quota signals, and task affinity. An explicitly selected center still overrides adaptive routing while it is available.

## Benchmark Token Savings

```bash
./scripts/harness-benchmark /path/to/repo "auth flow debug"
```

The benchmark estimates raw text tokens versus a compact context pack. It is not billing data, but it is the fastest way to check whether the harness is reducing context before cloud calls.

Compact noisy command output before a handoff:

```bash
./scripts/harness-compact-output command.log 4000
some-command 2>&1 | ./scripts/harness-compact-output - 4000
```

The compactor removes timestamp-only differences, annotates repeated lines, prioritizes critical errors, and enforces a hard character cap.

## Anthropic-Style Project Init

```bash
./scripts/harness-init-project /path/to/repo "Feature one" "Feature two"
./scripts/harness-features next /path/to/repo/feature_list.json
./scripts/harness-evaluate /path/to/repo "tests passed,handoff recorded" "tests passed" "handoff recorded"
```

Features are default-fail: `passes` starts as `false`, and completion requires evidence.

For center changes, prefer structured handoffs with a task fingerprint, evidence paths, and compact context-pack reference. Validate the generated manifest with:

```bash
./scripts/harness-handoff validate production_artifacts/handoffs/<handoff>.json
```

## Token Ledger

```bash
./scripts/harness-usage record production_artifacts/usage.jsonl claude 1200 150 0.04 "debug-auth"
./scripts/harness-usage report production_artifacts/usage.jsonl
```

## A/B Token Experiments

```bash
./scripts/harness-experiment record production_artifacts/experiments.jsonl auth-v1 auth-flow-v1 claude baseline 12000 900 0.12
./scripts/harness-experiment record production_artifacts/experiments.jsonl auth-v1 auth-flow-v1 claude harness 4200 650 0.05
./scripts/harness-experiment report production_artifacts/experiments.jsonl
./scripts/harness-experiment ingest-codex production_artifacts/experiments.jsonl auth-v2 auth-flow-v2 baseline codex-output.jsonl
```

Pairs are default-fail unless baseline and harness runs share the same task fingerprint and center, both succeed, baseline tokens are non-zero, and the harness run stays within the quality tolerance. Claude JSON ingestion counts normal input, cache creation, and cache-read tokens. Codex `--json` ingestion ignores warning lines and requires an actual usage event; quota-error output without usage is rejected instead of becoming a false zero-token result.

`./scripts/harness-health` remains constrained until valid, quality-preserving pairs exist for Codex, Claude, and Antigravity and each center shows positive average token savings.

Initialize and inspect the reproducible experiment queue:

```bash
./scripts/harness-experiment-queue init
./scripts/harness-experiment-queue next
./scripts/harness-experiment-queue blueprint
./scripts/harness-experiment-queue prepare
```

The scheduler prefers Claude, then Codex, then Antigravity among centers that are currently ready. It runs baseline before harness for the same task fingerprint and declares Antigravity usage ingestion as manual because the current `agy` CLI exposes no machine-readable token usage output. `blueprint` returns a dry-run command and artifact layout; `prepare` writes prompt, schema, and manifest files. Neither command executes a cloud center.

Before recording a run, score its structured output:

```bash
./scripts/harness-experiment-quality <output.json>
```

The evaluator checks the 250-word budget, exactly five distinct citations that resolve to real files inside the repository, and exactly three non-empty risks. Its deterministic `quality_score` is suitable for the paired experiment quality guard.

## Continuous Research Registry

```bash
./scripts/harness-research due production_artifacts/research_registry.json
./scripts/harness-research report production_artifacts/research_registry.json
./scripts/harness-research refresh production_artifacts/research_registry.json
```

The registry tracks official Codex, Anthropic, Ollama, and MCP sources with refresh cadence, content hashes, and findings. HTML is canonicalized to visible text before hashing so dynamic scripts do not create false change events. Changelog sources refresh more often than stable specifications. Treat release candidates and roadmaps as watch channels, not stable implementation requirements.

## Capability Lifecycle

```bash
./scripts/harness-capabilities scaffold <name> "<description>"
./scripts/harness-capabilities evaluate <name> <evidence-path...>
./scripts/harness-capabilities promote <name> <evidence-path...>
```

Capabilities begin as drafts. Promotion requires a skill, tool spec, non-empty MCP tool contract, documentation files, and real evidence paths. `memory-auditor` is the first promoted active capability.

## Local Search Index

```bash
./scripts/harness-index build /path/to/repo production_artifacts/indexes/repo.json
./scripts/harness-index search production_artifacts/indexes/repo.json "auth login token"
```

## Contextual Context Packs

```bash
./scripts/harness-contextual /path/to/repo "auth login token" 5
```

Contextual packs add path, query, nearest symbol or heading, and local relevance metadata before each snippet. Use this before handing compact context to Codex, Claude, Antigravity, or a local worker.

For code-heavy retrieval, prefer the hybrid chunk ranker:

```bash
./scripts/harness-hybrid-context /path/to/repo "rotate token auth service" 5
```

It uses BM25-like chunk scoring, path/symbol boosts, line ranges, and file diversity so one large file cannot consume the entire compact pack.

When live machine pressure allows it, the semantic index adds cached Ollama embeddings:

```bash
./scripts/harness-semantic-index plan embeddinggemma
./scripts/harness-semantic-index build /path/to/repo production_artifacts/indexes/semantic.json embeddinggemma
./scripts/harness-semantic-index search production_artifacts/indexes/semantic.json "authentication flow" embeddinggemma
```

Unchanged chunk vectors are reused by content hash. The planner falls back to hybrid lexical retrieval when swap/RAM is unsafe and does not pull or load a model in that state.

Retrieval quality is evaluated separately from token size:

```bash
./scripts/harness-retrieval-eval . production_artifacts/evals/harness-retrieval.json 5
```

The evaluator is default-fail and reports Recall@K plus MRR. A compact pack is not considered good merely because it is small.

## Structured Local Worker Plan

```bash
./scripts/harness-structured-worker complex '{"type":"object","properties":{"summary":{"type":"string"}},"required":["summary"]}' "summarize repo evidence"
```

This plans a gated Ollama structured-output request. If live swap/RAM state is unsafe, it returns an extractive/contextual-RAG fallback instead of trying to run a local model.

For more complex local work, plan a structured RAG pipeline:

```bash
./scripts/harness-local-pipeline 12 "analyze architecture and identify risks"
```

On a healthy machine, the plan uses retrieval, optional semantic reranking, structured map batches, reduce, and schema verification with concurrency capped at one. Under pressure it returns a retrieval-only plan and never loads Ollama.

## MCP Server

```bash
python3 -m harness_mcp.server
```

Codex and Claude use this same server. Antigravity uses the plugin skill plus CLI handoff until a direct MCP command is exposed.

Initialization negotiates stable MCP `2025-11-25` and preserves supported `2025-06-18` and `2024-11-05` clients.

Run protocol-level conformance after MCP changes:

```bash
./scripts/harness-mcp-check
./scripts/harness-mcp-security
./scripts/harness-context-pack-audit
./scripts/harness-codex-preflight "repo-heavy task" --local
```

This starts a fresh subprocess and checks initialize negotiation, tools, resources, prompts, JSON-only stdout, and duplicate tool names.

The security audit checks for unsafe shell execution, verifies command-policy exposure, probes `curl | sh` denial, and ensures generated experiment command blueprints are explicitly non-executing.

The context-pack audit checks generated RAG handoffs for per-pack size budgets, source/path provenance, and code-fenced evidence before they are sent to a cloud center.

Use `harness_aggregate_health` or `./scripts/harness-health` to combine these protocol results with tests, retrieval evaluation, research freshness, live center readiness, and campaign status.

Current MCP tools: route/set center, delegate Claude/Antigravity, benchmark context, initialize projects, manage default-fail feature lists, evaluate evidence, record/report token usage, run paired A/B token experiments, maintain the research registry, build/search local indexes, build contextual context packs, plan gated local structured workers, and run `harness_doctor` drift checks.
