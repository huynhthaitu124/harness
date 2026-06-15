from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_core.context_budget import build_context_pack
from harness_core.memory_index import record_memory

_LANGUAGE_CONFIG_FILES: dict[str, tuple[str, str]] = {
    "package.json": ("javascript", "node"),
    "pyproject.toml": ("python", ""),
    "setup.py": ("python", ""),
    "setup.cfg": ("python", ""),
    "go.mod": ("go", ""),
    "Cargo.toml": ("rust", ""),
    "pom.xml": ("java", "maven"),
    "build.gradle": ("java", "gradle"),
    "composer.json": ("php", ""),
    "Gemfile": ("ruby", "rails"),
    "mix.exs": ("elixir", "phoenix"),
}

# Glob-based detection for languages that don't have a single root config file
_LANGUAGE_GLOB_PATTERNS: list[tuple[str, str, str]] = [
    ("*.sln", "csharp", ""),
    ("*.csproj", "csharp", ""),
    ("*.fsproj", "fsharp", ""),
    ("*.vbproj", "visualbasic", ""),
    ("pubspec.yaml", "dart", "flutter"),
    ("deno.json", "typescript", "deno"),
    ("tsconfig.json", "typescript", ""),
]

_CSHARP_FRAMEWORK_HINTS: list[tuple[str, str]] = [
    ("aspnetcore", "asp.net core"),
    ("asp.net", "asp.net mvc"),
    ("blazor", "blazor"),
    ("maui", "maui"),
    ("wcf", "wcf"),
    ("azure functions", "azure functions"),
    ("azure cloud service", "azure cloud service"),
    ("entity framework", "entity framework"),
]

_FRAMEWORK_HINTS: dict[str, list[str]] = {
    "next": ("javascript", "next.js"),
    "nextjs": ("javascript", "next.js"),
    "nuxt": ("javascript", "nuxt"),
    "react": ("javascript", "react"),
    "vue": ("javascript", "vue"),
    "angular": ("javascript", "angular"),
    "express": ("javascript", "express"),
    "fastapi": ("python", "fastapi"),
    "django": ("python", "django"),
    "flask": ("python", "flask"),
    "fastify": ("javascript", "fastify"),
    "nestjs": ("javascript", "nestjs"),
    "gin": ("go", "gin"),
    "echo": ("go", "echo"),
    "axum": ("rust", "axum"),
    "actix": ("rust", "actix"),
}

_LANGUAGE_RESEARCH_KEYWORDS: dict[str, list[str]] = {
    "csharp": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "nuget", "msbuild", "azure", "migrations", "entity framework"],
    "typescript": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "npm", "tsc", "types"],
    "python": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "nghiên cứu", "đọc code", "pip", "poetry", "pytest"],
    "javascript": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "npm", "yarn", "pnpm", "bundle"],
    "go": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "go mod", "goroutine"],
    "rust": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "cargo", "crate"],
    "java": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "maven", "gradle"],
    "ruby": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "đọc code", "gem", "bundler"],
    "_default": ["research", "scan", "codebase", "log", "summarize", "tổng hợp", "nghiên cứu", "đọc repo", "đọc code"],
}

_LANGUAGE_CODING_KEYWORDS: dict[str, list[str]] = {
    "csharp": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup", "msbuild", "nuget", "migration", "controller", "razor"],
    "typescript": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup", "tsc", "lint", "build"],
    "python": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup", "pytest", "mypy"],
    "javascript": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup", "lint", "build"],
    "go": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup", "go test", "go build"],
    "rust": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup", "cargo test", "clippy"],
    "_default": ["implement", "fix", "refactor", "code", "test", "sửa", "cài", "setup"],
}

_INITIAL_FEATURES_BY_TYPE: dict[str, list[str]] = {
    "csharp": [
        "Harness initialization complete",
        "Solution builds successfully (msbuild)",
        "RAG index built",
        "Context packs generated for key controllers and services",
        "Memory seeded with architecture overview",
    ],
    "typescript": [
        "Harness initialization complete",
        "Type-check passes (tsc --noEmit)",
        "RAG index built",
        "Context packs generated for key modules",
        "Memory seeded with architecture overview",
    ],
    "python": [
        "Harness initialization complete",
        "Test suite passing",
        "RAG index built",
        "Context packs generated for key modules",
        "Memory seeded with architecture overview",
    ],
    "javascript": [
        "Harness initialization complete",
        "Test suite passing",
        "RAG index built",
        "Context packs generated for key routes and components",
        "Memory seeded with architecture overview",
    ],
    "go": [
        "Harness initialization complete",
        "Tests passing (go test ./...)",
        "RAG index built",
        "Context packs generated for key packages",
        "Memory seeded with architecture overview",
    ],
    "rust": [
        "Harness initialization complete",
        "Tests passing (cargo test)",
        "RAG index built",
        "Context packs generated for key crates",
        "Memory seeded with architecture overview",
    ],
    "_default": [
        "Harness initialization complete",
        "RAG index built",
        "Context packs generated",
        "Memory seeded with architecture overview",
    ],
}


def detect_project_type(root: Path) -> dict[str, Any]:
    language = "unknown"
    framework = ""
    config_file = ""
    entry_points: list[str] = []

    for filename, (lang, fw) in _LANGUAGE_CONFIG_FILES.items():
        if (root / filename).exists():
            language = lang
            framework = fw
            config_file = filename
            break

    # Glob-based fallback for languages without a single root config file
    if language == "unknown":
        for pattern, lang, fw in _LANGUAGE_GLOB_PATTERNS:
            matches = list(root.glob(pattern))
            if matches:
                language = lang
                framework = fw
                config_file = matches[0].name
                break

    if language == "javascript" and config_file == "package.json":
        try:
            pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            for hint, (_, fw) in _FRAMEWORK_HINTS.items():
                if any(hint in k.lower() for k in deps):
                    framework = fw
                    break
            main = pkg.get("main") or pkg.get("exports", {})
            if isinstance(main, str):
                entry_points.append(main)
        except Exception:
            pass

    if language == "python":
        for candidate in ("main.py", "app.py", "src/main.py", "src/app.py"):
            if (root / candidate).exists():
                entry_points.append(candidate)
                break
        readme_lower = ""
        for readme in root.glob("README*"):
            try:
                readme_lower = readme.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                pass
        for hint, (_, fw) in _FRAMEWORK_HINTS.items():
            if hint in readme_lower and not framework:
                framework = fw
                break

    if language == "csharp":
        doc_text = ""
        for docfile in ("AGENTS.md", "CLAUDE.md", "README.md", "README.txt"):
            p = root / docfile
            if p.exists():
                try:
                    doc_text += p.read_text(encoding="utf-8", errors="ignore").lower()
                except Exception:
                    pass
        for hint, fw_name in _CSHARP_FRAMEWORK_HINTS:
            if hint in doc_text and not framework:
                framework = fw_name
                break
        sln_files = list(root.glob("*.sln"))
        if sln_files:
            config_file = sln_files[0].name
            entry_points.append(sln_files[0].name)

    return {
        "language": language,
        "framework": framework,
        "config_file": config_file,
        "entry_points": entry_points,
    }


def extract_key_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for pattern in ("README*", "readme*", "AGENTS.md", "HARNESS.md"):
        candidates.extend(root.glob(pattern))
    for name in ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "composer.json", "Gemfile"):
        p = root / name
        if p.exists():
            candidates.append(p)
    for name in ("main.py", "app.py", "index.js", "index.ts", "main.go", "main.rs", "src/main.py", "src/app.py", "src/index.ts"):
        p = root / name
        if p.exists():
            candidates.append(p)
    seen: set[Path] = set()
    result: list[Path] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def build_analysis_context(root: Path, key_files: list[Path], max_chars: int = 3000) -> str:
    if key_files:
        parts: list[str] = []
        budget = max_chars
        for path in key_files:
            if budget <= 0:
                break
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                snippet = text[: min(600, budget)]
                header = f"## {path.relative_to(root).as_posix()}\n"
                parts.append(header + snippet)
                budget -= len(header) + len(snippet)
            except Exception:
                continue
        if parts:
            return "\n\n".join(parts)
    return build_context_pack(root, "architecture overview entry points", max_files=6, max_chars_per_file=500)


def generate_routing_keywords(language: str, framework: str, extra_terms: list[str] | None = None) -> dict[str, list[str]]:
    research = list(_LANGUAGE_RESEARCH_KEYWORDS.get(language, _LANGUAGE_RESEARCH_KEYWORDS["_default"]))
    coding = list(_LANGUAGE_CODING_KEYWORDS.get(language, _LANGUAGE_CODING_KEYWORDS["_default"]))
    if framework:
        fw_lower = framework.lower()
        if fw_lower not in research:
            research.append(fw_lower)
        if fw_lower not in coding:
            coding.append(fw_lower)
    for term in extra_terms or []:
        t = term.lower()
        if t not in research:
            research.append(t)
    return {"research_heavy_keywords": research, "coding_keywords": coding}


def generate_initial_features(language: str) -> list[str]:
    return list(_INITIAL_FEATURES_BY_TYPE.get(language, _INITIAL_FEATURES_BY_TYPE["_default"]))


def generate_initial_memories(analysis: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    name = root.name
    language = analysis.get("language", "unknown")
    framework = analysis.get("framework", "")
    config_file = analysis.get("config_file", "")
    entry_points = analysis.get("entry_points", [])

    stack_desc = language
    if framework:
        stack_desc = f"{language}/{framework}"

    memories = [
        {
            "content": f"Project '{name}' uses {stack_desc}. Config file: {config_file or 'unknown'}.",
            "kind": "operational",
            "tags": ["project", "tech-stack"],
            "importance": 0.9,
            "source": config_file or "harness-init",
        },
    ]
    if entry_points:
        memories.append(
            {
                "content": f"Main entry points for '{name}': {', '.join(entry_points)}.",
                "kind": "operational",
                "tags": ["project", "entry-point"],
                "importance": 0.8,
                "source": entry_points[0],
            }
        )
    memories.append(
        {
            "content": f"Harness initialized for '{name}' on {datetime.now(timezone.utc).date().isoformat()}. State in .harness/, artifacts in production_artifacts/.",
            "kind": "operational",
            "tags": ["harness", "init"],
            "importance": 0.7,
            "source": "harness-init",
        }
    )
    return memories


def seed_memories(memory_path: Path, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for m in memories:
        result = record_memory(
            memory_path,
            content=m["content"],
            source=m["source"],
            kind=m["kind"],
            tags=m.get("tags"),
            importance=m.get("importance", 0.5),
        )
        results.append(result)
    return results


def render_harness_md(analysis: dict[str, Any], harness_scripts_path: Path, project_name: str) -> str:
    language = analysis.get("language", "unknown")
    framework = analysis.get("framework", "")
    project_type = f"{language}/{framework}" if framework else language
    today = datetime.now(timezone.utc).date().isoformat()
    scripts = harness_scripts_path.as_posix()

    return f"""\
# Harness — {project_name}

> Generated by `harness init` on {today}. Edit sections marked [CUSTOMIZE].

## Project Profile
- Language: {language}
- Framework: {framework or "—"}
- Type: {project_type}
- Harness scripts: `{scripts}`

## Quick Start

```bash
harness-route "<task description>"     # select the optimal center for a task
harness-hybrid-context "<query>"       # build a compact context pack
harness-health                          # check system health
harness-memory search "<query>"        # search operational memory
```

## Center Selection

- `auto` — router picks the best center based on task type and quota
- `codex` — heavy code generation, repo-wide refactors
- `claude` — compact review, quick fixes, low-token tasks
- `antigravity` — broad research, large context budget

Switch center: `harness-center set <center>`

## Context Economy

Always use a context pack instead of raw file dumps:
- `harness-hybrid-context "<query>"` — BM25 + path/symbol boost
- `harness-contextual "<query>"` — snippets annotated with path and symbol context

Target: 50-75% token savings vs. raw context.

## Handoffs

Record a handoff when switching centers:
```bash
harness-handoff record --title "..." --from claude --to codex
```
Files are written to: `production_artifacts/handoffs/`

## Memory

```bash
harness-memory search "<query>"     # search memories
harness-memory pack "<query>"       # build a memory context pack
harness-memory sync                 # sync from artifacts
```

## MCP Server

Configured in: `configs/claude-mcp.json`

```
HARNESS_STATE_PATH    → .harness/state.json
HARNESS_ARTIFACTS_DIR → production_artifacts/
```

## [CUSTOMIZE] Project-Specific Notes

> **This section is empty.** Run the grill session to fill it in:
>
> ```bash
> harness-grill-project {project_name}
> ```
>
> The grill session asks targeted questions about this project's architecture,
> conventions, and constraints, then writes the answers here automatically.
> Any agent reading this file should run the grill session before starting work
> if this section still shows the placeholder above.

<!-- populated by harness-grill-project -->
"""


def generate_mcp_config(harness_root: Path, target_root: Path) -> dict[str, Any]:
    return {
        "mcpServers": {
            "harness": {
                "command": str(harness_root / "scripts" / "harness-mcp-server"),
                "args": [],
                "env": {
                    "HARNESS_STATE_PATH": str(target_root / ".harness" / "state.json"),
                    "HARNESS_ARTIFACTS_DIR": str(target_root / "production_artifacts"),
                },
            }
        }
    }


_GRILL_COMMON: list[dict[str, str]] = [
    {"key": "architecture", "q": "Briefly describe the overall architecture (e.g. monolith, microservices, layers):"},
    {"key": "entry_points", "q": "What are the main entry points / top-level executables or services?"},
    {"key": "test_command", "q": "What command runs the full test suite?"},
    {"key": "deploy_process", "q": "How is the project deployed (CI pipeline, manual, platform)?"},
    {"key": "conventions", "q": "Any naming or code conventions agents must follow (e.g. file structure, patterns)?"},
    {"key": "constraints", "q": "Known constraints or things agents must NOT do?"},
]

_GRILL_BY_LANGUAGE: dict[str, list[dict[str, str]]] = {
    "csharp": [
        {"key": "solution_projects", "q": "Which .csproj projects are core vs. utilities?"},
        {"key": "ef_migration", "q": "How are Entity Framework migrations applied?"},
        {"key": "azure_resources", "q": "List key Azure resources (App Service, Function App, Storage, etc.):"},
        {"key": "auth_approach", "q": "How is authentication handled (ASP.NET Identity, JWT, Azure AD, etc.)?"},
    ],
    "python": [
        {"key": "venv_setup", "q": "How is the virtual environment set up (venv, poetry, conda)?"},
        {"key": "lint_check", "q": "What linting/type-checking tools are used (ruff, mypy, flake8)?"},
        {"key": "db_migration", "q": "How are database migrations run (Alembic, Django migrations, other)?"},
    ],
    "javascript": [
        {"key": "build_command", "q": "What is the build command (npm run build, yarn build, etc.)?"},
        {"key": "env_vars", "q": "List critical env vars (names only, no values):"},
        {"key": "api_structure", "q": "Where do API routes live and how are they organized?"},
    ],
    "typescript": [
        {"key": "build_command", "q": "What is the build/compile command?"},
        {"key": "env_vars", "q": "List critical env vars (names only, no values):"},
        {"key": "strict_rules", "q": "Any TypeScript strict rules agents must enforce (no `any`, etc.)?"},
    ],
    "go": [
        {"key": "module_path", "q": "What is the Go module path?"},
        {"key": "key_packages", "q": "List the key internal packages:"},
        {"key": "env_vars", "q": "List critical env vars (names only, no values):"},
    ],
    "rust": [
        {"key": "workspace", "q": "Is this a Cargo workspace? List key crates:"},
        {"key": "features", "q": "Any important Cargo features agents should know about?"},
    ],
}


def generate_grill_questions(language: str, framework: str) -> list[dict[str, str]]:
    questions = list(_GRILL_COMMON)
    questions.extend(_GRILL_BY_LANGUAGE.get(language, []))
    return questions


def run_grill_session(
    target_root: Path,
    language: str,
    framework: str,
    project_name: str,
) -> dict[str, str]:
    questions = generate_grill_questions(language, framework)
    answers: dict[str, str] = {}
    print(f"\n=== Harness Grill Session — {project_name} ({language}/{framework or 'unknown'}) ===")
    print("Answer each question. Press Enter to skip.\n")
    for item in questions:
        try:
            answer = input(f"{item['q']}\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGrill session interrupted.")
            break
        if answer:
            answers[item["key"]] = answer
    return answers


def write_grill_answers_to_harness_md(harness_md_path: Path, answers: dict[str, str]) -> None:
    if not harness_md_path.exists() or not answers:
        return
    lines: list[str] = []
    for key, value in answers.items():
        label = key.replace("_", " ").title()
        lines.append(f"- **{label}**: {value}")
    customize_block = "\n".join(lines)
    content = harness_md_path.read_text(encoding="utf-8")
    old_marker = "<!-- populated by harness-grill-project -->"
    new_block = f"{customize_block}\n\n<!-- populated by harness-grill-project -->"
    updated = content.replace(old_marker, new_block)
    harness_md_path.write_text(updated, encoding="utf-8")


def render_harness_html(analysis: dict[str, Any], project_name: str, harness_scripts_path: Path) -> str:
    language = analysis.get("language", "unknown")
    framework = analysis.get("framework", "")
    project_type = f"{language}/{framework}" if framework else language
    today = datetime.now(timezone.utc).date().isoformat()
    scripts = harness_scripts_path.as_posix()
    research_kw = ", ".join(analysis.get("routing_keywords", {}).get("research_heavy_keywords", [])[:8])
    coding_kw = ", ".join(analysis.get("routing_keywords", {}).get("coding_keywords", [])[:8])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Harness — {project_name}</title>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
    --text: #e2e8f0; --muted: #8892a4; --accent: #7c6af7;
    --green: #4ade80; --amber: #fbbf24; --blue: #60a5fa; --red: #f87171;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; padding: 2rem; }}
  h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1rem; font-weight: 600; color: var(--accent); margin: 2rem 0 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .meta {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; }}
  .card-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem; }}
  .card-value {{ font-size: 1rem; font-weight: 600; }}
  .flow {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .center-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem 1rem; min-width: 130px; }}
  .center-box .name {{ font-weight: 700; font-size: 0.9rem; }}
  .center-box .desc {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }}
  .center-box.auto {{ border-color: var(--accent); }}
  .center-box.codex {{ border-color: var(--blue); }}
  .center-box.claude {{ border-color: var(--green); }}
  .center-box.antigravity {{ border-color: var(--amber); }}
  .arrow {{ color: var(--muted); font-size: 1.2rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
  td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }}
  tr:last-child td {{ border-bottom: none; }}
  code {{ background: var(--border); padding: 0.1em 0.4em; border-radius: 4px; font-family: monospace; font-size: 0.85em; }}
  .tag {{ display: inline-block; background: var(--border); color: var(--muted); padding: 0.1em 0.5em; border-radius: 4px; font-size: 0.75rem; margin: 0.1em; }}
  .section {{ margin-bottom: 2rem; }}
  .routing-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; }}
  .routing-row {{ display: flex; gap: 2rem; flex-wrap: wrap; }}
  .routing-col {{ flex: 1; min-width: 200px; }}
  .routing-col h3 {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
  footer {{ margin-top: 3rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); padding-top: 1rem; }}
</style>
</head>
<body>

<h1>⚡ Harness — {project_name}</h1>
<p class="meta">Generated {today} &nbsp;·&nbsp; {project_type} &nbsp;·&nbsp; scripts: <code>{scripts}</code></p>

<div class="grid">
  <div class="card"><div class="card-label">Language</div><div class="card-value">{language}</div></div>
  <div class="card"><div class="card-label">Framework</div><div class="card-value">{framework or "—"}</div></div>
  <div class="card"><div class="card-label">Config</div><div class="card-value">{analysis.get("config_file") or "—"}</div></div>
  <div class="card"><div class="card-label">Entry Point</div><div class="card-value">{(analysis.get("entry_points") or ["—"])[0]}</div></div>
</div>

<h2>How It Works</h2>
<div class="section">
  <p style="color:var(--muted);font-size:0.85rem;margin-bottom:1rem;">
    Every task flows through the router. The router reads live quota, observed token usage, and task keywords to pick the best center.
    Context is compressed into a pack before any cloud call. Results and handoffs are recorded to <code>production_artifacts/</code>.
  </p>
  <div class="flow">
    <div class="center-box auto"><div class="name">🔀 auto</div><div class="desc">Router — picks center<br>by quota + task type</div></div>
    <span class="arrow">→</span>
    <div class="center-box codex"><div class="name">🔵 codex</div><div class="desc">Heavy codegen<br>repo-wide refactor</div></div>
    <span class="arrow">·</span>
    <div class="center-box claude"><div class="name">🟢 claude</div><div class="desc">Compact review<br>quick fixes</div></div>
    <span class="arrow">·</span>
    <div class="center-box antigravity"><div class="name">🟡 antigravity</div><div class="desc">Broad research<br>large context</div></div>
  </div>
</div>

<h2>Routing Policy — {project_name}</h2>
<div class="section">
  <div class="routing-box">
    <div class="routing-row">
      <div class="routing-col">
        <h3>Research triggers (→ RAG first)</h3>
        {''.join(f'<span class="tag">{kw}</span>' for kw in analysis.get("routing_keywords", {}).get("research_heavy_keywords", []))}
      </div>
      <div class="routing-col">
        <h3>Coding triggers (→ prefer Codex)</h3>
        {''.join(f'<span class="tag">{kw}</span>' for kw in analysis.get("routing_keywords", {}).get("coding_keywords", []))}
      </div>
    </div>
  </div>
</div>

<h2>Context Economy</h2>
<div class="section">
  <table>
    <thead><tr><th>Command</th><th>What it does</th><th>When to use</th></tr></thead>
    <tbody>
      <tr><td><code>harness-hybrid-context "&lt;q&gt;"</code></td><td>BM25 + path/symbol boost</td><td>Default — most tasks</td></tr>
      <tr><td><code>harness-contextual "&lt;q&gt;"</code></td><td>Annotated snippets with symbol context</td><td>When symbol precision matters</td></tr>
      <tr><td><code>harness-memory pack "&lt;q&gt;"</code></td><td>Scored operational memories</td><td>Before any cloud delegation</td></tr>
      <tr><td><code>harness-codex-preflight</code></td><td>Memory + RAG + optional local model</td><td>Before handing off to Codex</td></tr>
    </tbody>
  </table>
</div>

<h2>Key Commands</h2>
<div class="section">
  <table>
    <thead><tr><th>Command</th><th>Purpose</th></tr></thead>
    <tbody>
      <tr><td><code>harness-route "&lt;task&gt;"</code></td><td>Select optimal center for a task</td></tr>
      <tr><td><code>harness-health</code></td><td>Aggregate health check (tests, doctor, MCP, retrieval)</td></tr>
      <tr><td><code>harness-doctor</code></td><td>Detect drift between tools, scripts, and docs</td></tr>
      <tr><td><code>harness-grill-project &lt;path&gt;</code></td><td>Interactive session to fill HARNESS.md [CUSTOMIZE]</td></tr>
      <tr><td><code>harness-memory search "&lt;q&gt;"</code></td><td>Search project operational memory</td></tr>
      <tr><td><code>harness-handoff record ...</code></td><td>Record a center-to-center handoff</td></tr>
      <tr><td><code>harness-autopilot plan</code></td><td>Suggest next bounded action</td></tr>
      <tr><td><code>harness-center set &lt;center&gt;</code></td><td>Override center preference</td></tr>
    </tbody>
  </table>
</div>

<h2>Data Layout</h2>
<div class="section">
  <table>
    <thead><tr><th>Path</th><th>Contents</th></tr></thead>
    <tbody>
      <tr><td><code>.harness/state.json</code></td><td>Center preferences, quotas, routing policy</td></tr>
      <tr><td><code>.harness/project.json</code></td><td>Language, framework, analyzed_at</td></tr>
      <tr><td><code>.harness/index.json</code></td><td>BM25 search index</td></tr>
      <tr><td><code>production_artifacts/memory.jsonl</code></td><td>Operational memories (JSONL, content-hash deduped)</td></tr>
      <tr><td><code>production_artifacts/feature_list.json</code></td><td>Default-fail feature tracker</td></tr>
      <tr><td><code>production_artifacts/handoffs/</code></td><td>Structured center-to-center handoff files</td></tr>
      <tr><td><code>production_artifacts/context_packs/</code></td><td>Pre-built compact context for cloud calls</td></tr>
      <tr><td><code>configs/claude-mcp.json</code></td><td>MCP server config pointing to Harness scripts</td></tr>
      <tr><td><code>HARNESS.md</code></td><td>Agent-readable guidelines + project conventions</td></tr>
      <tr><td><code>HARNESS.html</code></td><td>This file — visual architecture overview</td></tr>
    </tbody>
  </table>
</div>

<footer>Harness · {project_name} · {today}</footer>
</body>
</html>
"""
