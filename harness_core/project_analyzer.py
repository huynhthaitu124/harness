from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_core.context_budget import build_context_pack
from harness_core.memory_index import record_memory

# ── Agent / AI tool detection ─────────────────────────────────────────────────
# Each entry: (dir_or_file_pattern, agent_name, description)
# Checked at root level first, then one subdir deep for monorepos.
_AGENT_SIGNALS: list[tuple[str, str, str]] = [
    # directories
    (".agents",          "Antigravity",  "rules, skills, resources"),
    (".claude",          "Claude Code",  "project config"),
    (".codex-artifacts", "Codex",        "output artifacts"),
    (".codex-nightly",   "Codex Nightly","nightly run artifacts"),
    (".gemini",          "Gemini",       "project config"),
    (".cursor",          "Cursor",       "rules & settings"),
    (".continue",        "Continue",     "context config"),
    (".aider",           "Aider",        "settings"),
    (".codeium",         "Codeium",      "context"),
    # files
    ("AGENTS.md",        "OpenAI Codex", "agent instructions"),
    ("CLAUDE.md",        "Claude Code",  "agent instructions"),
    ("GEMINI.md",        "Gemini CLI",   "agent instructions"),
    (".mcp.json",        "MCP",          "server config"),
    ("mcp.json",         "MCP",          "server config"),
    ("copilot-instructions.md", "GitHub Copilot", "instructions"),
    (".github/copilot-instructions.md", "GitHub Copilot", "instructions"),
]


def detect_agents(root: Path) -> list[dict[str, str]]:
    """Scan root (and one level deep for monorepos) for AI agent configs.

    Returns list of {agent, path, description} dicts, deduplicated by agent name.
    """
    found: dict[str, dict] = {}  # agent_name → first occurrence

    def _check(p: Path, agent: str, desc: str) -> None:
        if p.exists() and agent not in found:
            rel = str(p.relative_to(root))
            found[agent] = {"agent": agent, "path": rel, "description": desc}

    for pattern, agent, desc in _AGENT_SIGNALS:
        _check(root / pattern, agent, desc)
        # one level deep (monorepo subdirs)
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith(".") and child.name not in {
                "node_modules", "dist", "build", "bin", "obj", "production_artifacts"
            }:
                _check(child / pattern, agent, desc)

    return list(found.values())


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


_DETECT_SKIP = frozenset({
    ".git", "node_modules", ".next", ".nuxt", ".svelte-kit",
    "dist", "build", "__pycache__", ".venv", "venv",
    "bin", "obj", "out", "target", "coverage", ".nyc_output",
    "vendor", "production_artifacts", ".harness",
})

# Priority order when scoring: higher = wins tie-breaks.
# Languages with explicit project files beat generic globs.
_LANG_PRIORITY: dict[str, int] = {
    "csharp":      100,
    "fsharp":      100,
    "visualbasic": 100,
    "java":         90,
    "python":       90,
    "go":           90,
    "rust":         90,
    "dart":         80,
    "ruby":         80,
    "elixir":       80,
    "php":          80,
    "typescript":   50,
    "javascript":   40,
}


def _scan_languages(root: Path) -> dict[str, dict]:
    """Scan entire repo and return score info per language.

    Returns {lang: {"score": int, "config_file": str, "matches": [Path]}}
    Single file-tree walk — O(N) regardless of how many patterns we check.
    """
    import fnmatch

    results: dict[str, dict] = {}

    def _skip_dir(name: str) -> bool:
        return name in _DETECT_SKIP

    # Build a fast name→[(lang, fw, pattern)] lookup
    exact_patterns: dict[str, list[tuple[str, str, str]]] = {}
    glob_patterns:  list[tuple[str, str, str]] = []   # (pattern, lang, fw)
    for pattern, lang, fw in _LANGUAGE_GLOB_PATTERNS:
        if "*" in pattern or "?" in pattern:
            glob_patterns.append((pattern, lang, fw))
        else:
            exact_patterns.setdefault(pattern, []).append((lang, fw, pattern))

    # Root-level config files — check before walking (highest weight)
    for filename, (lang, fw) in _LANGUAGE_CONFIG_FILES.items():
        p = root / filename
        if p.exists():
            r = results.setdefault(lang, {"score": 0, "config_file": "", "fw": fw, "matches": []})
            r["score"]      += 200
            r["config_file"] = r["config_file"] or filename
            r["matches"].append(p)

    # Single os.walk — prune skip dirs immediately
    import os
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
        dp    = Path(dirpath)
        depth = len(dp.relative_to(root).parts)

        for name in filenames:
            p = dp / name

            # exact pattern match (e.g. tsconfig.json, pyproject.toml)
            if name in exact_patterns:
                for lang, fw, pat in exact_patterns[name]:
                    weight = max(5, 60 - depth * 8)
                    r = results.setdefault(lang, {"score": 0, "config_file": "", "fw": fw, "matches": []})
                    r["score"]      += weight
                    r["config_file"] = r["config_file"] or name
                    r["matches"].append(p)

            # glob pattern match (e.g. *.csproj, *.sln)
            for pattern, lang, fw in glob_patterns:
                if fnmatch.fnmatch(name, pattern):
                    weight = max(5, 60 - depth * 8)
                    r = results.setdefault(lang, {"score": 0, "config_file": "", "fw": fw, "matches": []})
                    r["score"]      += weight
                    r["config_file"] = r["config_file"] or name
                    r["matches"].append(p)

    return results


def detect_project_type(root: Path) -> dict[str, Any]:
    lang_scores = _scan_languages(root)

    if not lang_scores:
        return {
            "language": "unknown", "framework": "", "config_file": "",
            "entry_points": [], "secondary_languages": [],
        }

    # Pick winner: highest score, tie-broken by _LANG_PRIORITY
    def _rank(item):
        lang, info = item
        return (info["score"], _LANG_PRIORITY.get(lang, 0))

    ranked = sorted(lang_scores.items(), key=_rank, reverse=True)
    primary_lang, primary_info = ranked[0]

    language    = primary_lang
    framework   = primary_info.get("fw", "")
    config_file = primary_info["config_file"]
    entry_points: list[str] = []

    # ── per-language post-processing ──────────────────────────────────────────

    if language in ("javascript", "typescript"):
        # look for package.json at root or first subdir
        for pkg_path in [root / "package.json"] + list(root.glob("*/package.json"))[:3]:
            if pkg_path.exists():
                try:
                    pkg  = json.loads(pkg_path.read_text(encoding="utf-8"))
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    for hint, (_, fw) in _FRAMEWORK_HINTS.items():
                        if any(hint in k.lower() for k in deps):
                            framework = fw
                            break
                    main = pkg.get("main")
                    if isinstance(main, str):
                        entry_points.append(main)
                    if framework:
                        break
                except Exception:
                    pass

    if language == "python":
        for candidate in ("main.py", "app.py", "src/main.py", "src/app.py"):
            if (root / candidate).exists():
                entry_points.append(candidate)
                break
        readme_lower = ""
        for readme in list(root.glob("README*"))[:1]:
            try:
                readme_lower = readme.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                pass
        for hint, (_, fw) in _FRAMEWORK_HINTS.items():
            if hint in readme_lower and not framework:
                framework = fw
                break

    if language == "csharp":
        csproj_files = [m for m in primary_info["matches"] if m.suffix == ".csproj"]
        sln_files    = [m for m in primary_info["matches"] if m.suffix == ".sln"]

        # Detect framework from .csproj SDK attribute (most reliable signal)
        if not framework:
            _SDK_TO_FW = {
                "microsoft.net.sdk.web":    "asp.net core",
                "microsoft.net.sdk.worker": "asp.net core worker",
                "microsoft.net.sdk.blazorwebassembly": "blazor",
                "microsoft.net.sdk.maui":   "maui",
            }
            for csproj in csproj_files[:20]:
                try:
                    content = csproj.read_text(encoding="utf-8", errors="ignore").lower()
                    for sdk_key, fw_name in _SDK_TO_FW.items():
                        if sdk_key in content:
                            framework = fw_name
                            break
                except Exception:
                    pass
                if framework:
                    break

        # Fallback: scan doc files for framework hints
        if not framework:
            doc_text = ""
            for docfile in ("AGENTS.md", "CLAUDE.md", "README.md"):
                for p in [root / docfile] + list(root.glob(f"*/{docfile}"))[:2]:
                    if p.exists():
                        try:
                            doc_text += p.read_text(encoding="utf-8", errors="ignore").lower()
                        except Exception:
                            pass
            for hint, fw_name in _CSHARP_FRAMEWORK_HINTS:
                if hint in doc_text:
                    framework = fw_name
                    break

        # entry_points: prefer API/Gateway/Service projects, skip tests/migrations
        _TEST_HINTS   = ("test", "spec", "mock", "fixture")
        _SKIP_HINTS   = ("dbmigrat", "migration", "seed", "scaffold")
        _ENTRY_HINTS  = (".api", "gateway", "worker", "host")   # exact entry-point markers
        _LAYER_HINTS  = ("application", "domain", "infrastructure", "persistence",
                         "data", "shared", "common", "contracts", "abstractions")

        def _csproj_rank(p: Path) -> int:
            n = p.stem.lower()
            if any(h in n for h in _TEST_HINTS + _SKIP_HINTS):
                return 0                          # skip entirely
            if any(n.endswith(h) or h in n for h in _ENTRY_HINTS):
                return 3                          # real entry point
            if any(h in n for h in _LAYER_HINTS):
                return 1                          # internal layer — keep but low priority
            return 2                              # other service project

        if sln_files:
            config_file = sln_files[0].name
            entry_points.extend(str(s.relative_to(root)) for s in sln_files[:3])
        else:
            ranked_csprojs = sorted(
                [c for c in csproj_files if _csproj_rank(c) > 0],
                key=lambda p: -_csproj_rank(p),
            )
            entry_points.extend(str(p.relative_to(root)) for p in ranked_csprojs[:5])

    # ── secondary languages (monorepo) ────────────────────────────────────────
    secondary_langs: list[str] = []
    for lang, info in ranked[1:4]:
        if info["score"] >= 20 and lang != language:
            secondary_langs.append(lang)

    return {
        "language":           language,
        "framework":          framework,
        "config_file":        config_file,
        "entry_points":       entry_points,
        "secondary_languages": secondary_langs,
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
            "content": f"Harness initialized for '{name}' on {datetime.now(timezone.utc).date().isoformat()}. All data in .harness/ of the project.",
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


def _call_ollama(prompt: str, timeout: int = 60) -> str | None:
    """Call Ollama /api/generate. Returns text response or None on any failure."""
    import json as _json
    import os as _os
    import urllib.error
    import urllib.request
    host    = _os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    payload = _json.dumps({"model": "llama3.2", "prompt": prompt, "stream": False}).encode()
    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read())
            return data.get("response", "").strip() or None
    except Exception:
        return None


def _agents_md_prompt(analysis: dict[str, Any], root: Path) -> str:
    project_name = analysis.get("project_name", root.name)
    language     = analysis.get("language", "unknown")
    framework    = analysis.get("framework", "")
    entry_points = analysis.get("entry_points", [])
    context      = (analysis.get("context_snippet") or "")[:2000]

    fw  = f" / {framework}" if framework else ""
    eps = ", ".join(entry_points[:6]) if entry_points else "unknown"

    return f"""\
Write a concise AGENTS.md for the software project "{project_name}".

Tech stack : {language}{fw}
Entry points: {eps}

Project context (key file excerpts):
{context}

Rules:
- Under 250 words
- Markdown, no triple-backtick code blocks around the whole output
- Cover: (1) one-paragraph project overview, (2) essential build/test/run commands \
in a fenced block, (3) key conventions, (4) important source directories
- Be specific to THIS project; do NOT use placeholder text like "(add here)"
- If you cannot determine something from the context, omit that section entirely
- Do NOT include a harness or MCP section — that is injected separately

Return only the markdown, no preamble or commentary.\
"""


def generate_agents_md(analysis: dict[str, Any], root: Path) -> str:
    """Generate AGENTS.md for the target project.

    Tries Ollama first; falls back to a smart template when Ollama is
    unavailable or returns an empty response.  The harness block is NOT
    included here — it is appended by inject_agent_instructions() afterward.
    """
    llm = _call_ollama(_agents_md_prompt(analysis, root))
    if llm and len(llm.strip()) > 80:
        return llm.strip()

    # Template fallback
    project_name = analysis.get("project_name", root.name)
    language     = analysis.get("language", "unknown")
    framework    = analysis.get("framework", "")
    entry_points = analysis.get("entry_points", [])

    fw_line  = f" ({framework})" if framework else ""
    ep_block = "\n".join(f"- `{ep}`" for ep in entry_points[:6]) if entry_points else "- _(see project root)_"

    return f"""\
# {project_name}

{project_name} is a {language}{fw_line} project.

## Build & Test

```bash
# Add build, test, and run commands specific to this project
```

## Conventions

- Language: **{language}**{"  |  Framework: **" + framework + "**" if framework else ""}

## Entry Points

{ep_block}

## Key Directories

_(Document the main source directories and their purpose.)_
"""


def render_harness_md(analysis: dict[str, Any], harness_scripts_path: Path, project_name: str) -> str:
    language  = analysis.get("language", "unknown")
    framework = analysis.get("framework", "")
    today     = datetime.now(timezone.utc).date().isoformat()

    return f"""\
# Harness — {project_name}

> Generated {today}.  Full docs: open `HARNESS.html` in a browser.

## Project Profile

- Language  : {language}
- Framework : {framework or "—"}
- Root      : _(set at init)_

## Mandatory First Step

For **every task, bug, or ticket** — regardless of how it arrives:

1. **First tool call**: `harness_ticket_context(root=<project_root>, task=<message>)` via MCP
2. **If MCP unavailable**: `harness rag-pack "<task>" [--ticket ID]` → read `last-rag-pack.md`
3. **Never** call `list_dir`, `read_file`, `grep_search`, or `find` before step 1

## MCP Tools — Tier 1 (work loop)

| Tool | Parameters | When |
|------|-----------|------|
| `harness_ticket_context` | `root`, `task`, `ticket_id?`, `top_k?` | **First call** — RAG chunks + workflow + routing |
| `harness_route_task` | `task`, `root?` | Root unknown — lightweight routing |
| `harness_contextual_context_pack` | `root`, `query`, `top_k?` | More context mid-task |
| `harness_hybrid_context_pack` | `root`, `query`, `top_k?` | BM25 + symbol boost retrieval |
| `harness_search_memory` | `path`, `query` | Search prior decisions before implementing |
| `harness_record_memory` | `path`, `content`, `source`, `kind` | Save insight after task completes |

Full reference (all tools, 6 tiers): `.harness/mcp_schema.md`

## Project Docs

Open `HARNESS.html` for architecture, key modules, conventions, and ticket workflow.
"""


def generate_mcp_config(harness_root: Path, target_root: Path) -> dict[str, Any]:
    return {
        "mcpServers": {
            "harness": {
                "command": str(harness_root / "scripts" / "harness-mcp-server"),
                "args": [],
                "env": {
                    "HARNESS_STATE_PATH": str(target_root / ".harness" / "state.json"),
                    "HARNESS_ARTIFACTS_DIR": str(target_root / ".harness"),
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
            return answers
        if answer:
            answers[item["key"]] = answer

    # Ticket workflow is now inferred by the selected agent during `harness init`
    # (reads git log, branch names, CI config). No interactive questions needed.

    return answers


def write_grill_answers_to_harness_md(harness_md_path: Path, answers: dict[str, str]) -> None:
    if not harness_md_path.exists() or not answers:
        return

    # Grill answers no longer contain wf_* keys — workflow is agent-inferred during init.
    # Write only plain project-specific answers into the HARNESS.md marker block.
    plain = {k: v for k, v in answers.items() if not k.startswith("wf_")}
    lines: list[str] = []
    for key, value in plain.items():
        label = key.replace("_", " ").title()
        lines.append(f"- **{label}**: {value}")

    content = harness_md_path.read_text(encoding="utf-8")
    old_marker = "<!-- populated by harness-grill-project -->"
    new_block = "\n".join(lines) + f"\n\n{old_marker}"
    updated = content.replace(old_marker, new_block)
    harness_md_path.write_text(updated, encoding="utf-8")


def render_harness_html(  # noqa: C901
    analysis: dict[str, Any],
    project_name: str,
    harness_scripts_path: Path,
    *,
    agent_sections: "dict[str, Any] | None" = None,
    workflow: "dict[str, Any] | None" = None,
) -> str:
    language   = analysis.get("language", "unknown")
    framework  = analysis.get("framework", "") or ""
    today      = datetime.now(timezone.utc).date().isoformat()
    scripts    = harness_scripts_path.as_posix()

    # ── derived values ────────────────────────────────────────────────────────
    sec_langs     = analysis.get("secondary_languages", []) or []
    config_file   = analysis.get("config_file") or ""
    entry_points  = analysis.get("entry_points") or []
    agents        = analysis.get("agents") or []
    features      = analysis.get("initial_features") or []
    kw            = analysis.get("routing_keywords", {})

    research_kws  = kw.get("research_heavy_keywords", [])
    coding_kws    = kw.get("coding_keywords", [])

    # ── initials ──────────────────────────────────────────────────────────────
    words = project_name.strip().split()
    if len(words) >= 2:
        initials = (words[0][0] + words[1][0]).upper()
    else:
        initials = project_name[:2].upper()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _e(text: str) -> str:
        """HTML-escape a string."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def _pill(text: str, style: str = "") -> str:
        return f'<span class="pill" style="{style}">{_e(text)}</span>'

    def _tags(*labels: str) -> str:
        return '<span class="tags">' + "".join(f"<span>{_e(l)}</span>" for l in labels) + "</span>"

    def _fact(label: str, value: str) -> str:
        return f'<div class="fact"><span>{_e(label)}</span><span>{value}</span></div>'

    # ── agents block ──────────────────────────────────────────────────────────
    def _agent_rules() -> str:
        if not agents:
            return '<div class="rule"><span class="rule-id"><span class="group-code">—</span></span><span style="color:var(--muted)">No agent configs detected</span><small></small></div>'
        rows = []
        for a in agents:
            name   = a.get("name", str(a)) if isinstance(a, dict) else str(a)
            detail = a.get("config_file", "") if isinstance(a, dict) else ""
            rows.append(
                f'<div class="rule">'
                f'<span class="rule-id"><span class="group-code">{_e(name)}</span></span>'
                f'<span><code>{_e(detail)}</code></span>'
                f'<small>auto-detected</small>'
                f'</div>'
            )
        return "\n".join(rows)

    # ── features block ────────────────────────────────────────────────────────
    def _feature_rules() -> str:
        if not features:
            return '<div class="rule"><span class="rule-id"><span class="group-code">FEAT</span></span><span style="color:var(--muted)">No features configured</span><small></small></div>'
        rows = []
        for f in features:
            rows.append(
                f'<div class="rule">'
                f'<span class="rule-id"><span class="group-code">FEAT</span> <strong>{_e(str(f))}</strong></span>'
                f'<span>{_e(str(f))}</span>'
                f'<small><span class="pill" style="color:var(--muted);border-color:var(--line)">not-run</span></small>'
                f'</div>'
            )
        return "\n".join(rows)

    # ── routing keyword rules ─────────────────────────────────────────────────
    def _kw_rules(kw_words: list, group: str) -> str:
        if not kw_words:
            return f'<div class="rule" data-groups="{group}"><span class="rule-id"><span class="group-code">{group}</span></span><span style="color:var(--muted)">—</span><small></small></div>'
        rows = []
        for w in kw_words[:20]:
            rows.append(
                f'<div class="rule" data-groups="{group}">'
                f'<span class="rule-id"><span class="group-code">{group}</span></span>'
                f'<span>{_e(str(w))}</span>'
                f'<small></small>'
                f'</div>'
            )
        return "\n".join(rows)

    # ── profile fact rows ─────────────────────────────────────────────────────
    ep_facts = ""
    for ep in (entry_points or ["—"]):
        ep_facts += _fact("Entry point", f"<code>{_e(str(ep))}</code>")

    sec_lang_str = ", ".join(_e(str(l)) for l in sec_langs) if sec_langs else "—"

    # ── counts ────────────────────────────────────────────────────────────────
    kw_count   = len(research_kws) + len(coding_kws)
    agent_count = len(agents)
    feat_count  = len(features)

    # ── MCP context tool decisions ────────────────────────────────────────────
    mcp_tools = [
        ("HYB", "harness_hybrid_context_pack",    "blue",   "BM25 + path/symbol boost. Default for most tasks."),
        ("CTX", "harness_contextual_context_pack", "green",  "Annotated snippets with symbol context. Use when symbol precision matters."),
        ("LOC", "harness_local_context_pack",      "amber",  "Local LLM pre-summarises, then cloud call. Use for cost-sensitive tasks."),
        ("MEM", "harness_memory_pack",             "muted",  "Scored operational memories. Call before any delegation."),
        ("PRE", "harness_codex_preflight",         "blue",   "Memory + RAG + optional local model combined. Hand off to Codex."),
    ]

    def _mcp_decision(short: str, name: str, color: str, desc: str) -> str:
        color_map = {
            "blue":  "color:var(--blue);border-color:color-mix(in srgb,var(--blue) 35%,var(--line))",
            "green": "color:var(--green);border-color:color-mix(in srgb,var(--green) 35%,var(--line))",
            "amber": "color:var(--amber);border-color:color-mix(in srgb,var(--amber) 35%,var(--line))",
            "muted": "color:var(--muted);border-color:var(--line)",
            "red":   "color:var(--red);border-color:color-mix(in srgb,var(--red) 35%,var(--line))",
        }
        id_style = color_map.get(color, color_map["muted"])
        return (
            f'<div class="decision">'
            f'<span class="id" style="{id_style}">{_e(short)}</span>'
            f'<div><code style="font-size:12px">{_e(name)}</code><p style="margin:4px 0 0">{_e(desc)}</p></div>'
            f'</div>'
        )

    mcp_decisions_html = "\n".join(_mcp_decision(s, n, c, d) for s, n, c, d in mcp_tools)

    # ── workflow section HTML ─────────────────────────────────────────────────
    workflow_section_html = ""
    if workflow:
        wf_steps   = workflow.get("steps", [])
        wf_rules   = workflow.get("critical_rules", [])
        wf_system  = _e(workflow.get("ticket_system", ""))
        wf_url     = _e(workflow.get("ticket_url", ""))
        wf_branch  = _e(workflow.get("branch_pattern", ""))
        wf_base    = _e(workflow.get("base_branch", "main"))
        wf_build   = _e(workflow.get("build_cmd", ""))
        wf_files   = workflow.get("context_files", [])

        facts_rows = ""
        if wf_system:
            facts_rows += _fact("Ticket system", f"<strong>{wf_system}</strong>" + (f"  <small><a href='{wf_url}' target='_blank'>{wf_url}</a></small>" if wf_url else ""))
        if wf_branch:
            facts_rows += _fact("Branch pattern", f"<code>{wf_branch}</code> from <code>{wf_base}</code>")
        if wf_build:
            facts_rows += _fact("Verify cmd", f"<code>{wf_build}</code>")
        if wf_files:
            facts_rows += _fact("Load first", " ".join(f"<code>{_e(f)}</code>" for f in wf_files[:6]))

        step_rows = ""
        for s in wf_steps:
            sid    = _e(s.get("id", ""))
            stitle = _e(s.get("title", ""))
            sdet   = _e(s.get("detail", ""))
            step_rows += (
                f'<div class="rule">'
                f'<span class="rule-id"><span class="group-code">{sid}</span></span>'
                f'<span><strong>{stitle}</strong><br><small style="color:var(--muted)">{sdet}</small></span>'
                f'<small></small>'
                f'</div>'
            )

        rule_rows = ""
        for i, r in enumerate(wf_rules, 1):
            rule_rows += (
                f'<div class="rule">'
                f'<span class="rule-id"><span class="group-code">RULE-{i:02d}</span></span>'
                f'<span>{_e(r)}</span>'
                f'<small style="color:var(--red);font-weight:700">always</small>'
                f'</div>'
            )

        workflow_section_html = f"""
<!-- ── 08 Ticket Workflow ── -->
<section id="workflow">
  <div class="section-head">
    <span class="kicker">Work loop</span>
    <h2>Ticket workflow</h2>
    <p style="color:var(--muted);font-size:.95rem">Follow these steps for every ticket, bug, or feature request on this project.</p>
  </div>
  {'<div class="board">' + facts_rows + '</div>' if facts_rows else ''}
  {'<div class="rule-group" style="margin-top:24px"><div class="rule-group-head"><h3>Steps</h3></div>' + step_rows + '</div>' if step_rows else ''}
  {'<div class="rule-group" style="margin-top:24px"><div class="rule-group-head"><h3>Critical rules</h3></div>' + rule_rows + '</div>' if rule_rows else ''}
</section>"""

    # ── dynamic nav items ────────────────────────────────────────────────────
    _base_nav = [
        ("overview",  "Overview",  "00"),
        ("profile",   "Profile",   "01"),
        ("routing",   "Routing",   "02"),
        ("agents",    "Agents",    "03"),
        ("features",  "Features",  "04"),
        ("context",   "Context",   "05"),
        ("commands",  "Commands",  "06"),
        ("layout",    "Layout",    "07"),
    ]
    if workflow:
        _base_nav.append(("workflow", "Workflow", "08"))

    _extra_nav: list[tuple[str, str, str]] = []
    _agent_start = 9 if workflow else 8
    if agent_sections:
        for _i, _sec in enumerate(agent_sections.get("sections", []), start=8):
            _extra_nav.append((
                _sec.get("id", f"sec{_i:02d}"),
                _sec.get("title", f"Section {_i:02d}"),
                f"{_i:02d}",
            ))

    def _nav_link(href: str, label: str, num: str) -> str:
        return (
            f'    <a href="#{_e(href)}"><span>{_e(label)}</span>'
            f'<span class="num">{_e(num)}</span></a>'
        )

    nav_html = "\n".join(_nav_link(h, l, n) for h, l, n in _base_nav + _extra_nav)

    # ── agent-generated sections (08+) ───────────────────────────────────────
    def _render_agent_section(idx: int, sec: dict) -> str:
        sid      = _e(sec.get("id", f"sec{idx:02d}"))
        title    = _e(sec.get("title", f"Section {idx:02d}"))
        kicker   = _e(sec.get("kicker", ""))
        summary  = sec.get("summary", "")
        sec_type = sec.get("type", "prose")
        num      = f"{idx:02d}"

        summary_html = (
            f'<p style="color:var(--muted);font-size:.95rem">{_e(summary)}</p>'
            if summary else ""
        )

        content_html = ""
        if sec_type == "facts":
            fact_items = sec.get("facts", [])
            if fact_items:
                rows = "".join(
                    _fact(str(f), "") if isinstance(f, str)
                    else _fact(str(f.get("label", "")), _e(str(f.get("value", ""))))
                    for f in fact_items
                )
                content_html = f'<div class="board">{rows}</div>'
        elif sec_type == "rules":
            rule_items = sec.get("rules", [])
            if rule_items:
                rows = []
                for r in rule_items:
                    if isinstance(r, str):
                        rid, body, note = "", _e(r), ""
                    else:
                        rid   = _e(str(r.get("id", ""))[:28])
                        body  = _e(str(r.get("content", "")))
                        note  = _e(str(r.get("note", "")))
                    rows.append(
                        f'<div class="rule">'
                        f'<span class="rule-id"><span class="group-code">{rid}</span></span>'
                        f'<span>{body}</span>'
                        f'<small>{note}</small>'
                        f'</div>'
                    )
                content_html = (
                    f'<div class="rule-group">'
                    f'<div class="rule-group-head"><h3>{title}</h3></div>'
                    + "".join(rows) +
                    f'</div>'
                )

        agent_badge = (
            f'<span class="pill" style="color:var(--green);border-color:color-mix(in srgb,var(--green) 35%,var(--line));margin-left:8px">'
            f'agent-generated</span>'
        )

        return (
            f'\n<!-- ── {num} {title} ── -->\n'
            f'<section id="{sid}">\n'
            f'  <div class="section-head">\n'
            f'    <span class="kicker">{kicker}</span>\n'
            f'    <h2>{title}{agent_badge}</h2>\n'
            f'    {summary_html}\n'
            f'  </div>\n'
            f'  {content_html}\n'
            f'</section>'
        )

    agent_sections_html = ""
    if agent_sections:
        parts = []
        for _i, _sec in enumerate(agent_sections.get("sections", []), start=8):
            parts.append(_render_agent_section(_i, _sec))
        if parts:
            agent_name = _e(str(agent_sections.get("agent", "agent")))
            parts.insert(0,
                f'\n<div style="border-top:2px solid var(--ink);margin-bottom:40px;padding-top:24px">'
                f'<span class="kicker">Project-specific</span>'
                f'<h2 style="margin-top:4px">Deep research</h2>'
                f'<p style="color:var(--muted);font-size:.9rem">Generated by <strong>{agent_name}</strong> from live codebase analysis.</p>'
                f'</div>'
            )
        agent_sections_html = "\n".join(parts)

    return f"""<!DOCTYPE html>
<!-- Harness spec — {_e(project_name)} — {today} -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Harness — {_e(project_name)}</title>
<style>
:root {{
  --paper:#f5f2eb;
  --panel:#fffdf8;
  --ink:#172033;
  --muted:#667085;
  --line:#d8d0c2;
  --blue:#15476f;
  --green:#24745a;
  --amber:#9a6400;
  --red:#b42318;
}}
*,::before,::after{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%}}
body{{
  background:
    linear-gradient(90deg,rgba(23,32,51,.035) 1px,transparent 1px) 0 0/28px 28px,
    linear-gradient(rgba(23,32,51,.025) 1px,transparent 1px) 0 0/28px 28px,
    var(--paper);
  color:var(--ink);
  font:16px/1.55 Georgia,'Times New Roman',serif;
  min-height:100vh;
}}
h1,h2,h3,nav a,.kicker,button,input,th,strong{{
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}}
h1{{font-size:2rem;line-height:1.15;letter-spacing:-.02em;margin-bottom:12px}}
h2{{font-size:1.35rem;line-height:1.2;letter-spacing:-.01em;margin-bottom:8px}}
h3{{font-size:1.05rem;margin-bottom:6px}}
p{{margin-bottom:10px}}
strong{{font-weight:700}}
code{{
  font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;
  font-size:.82em;background:rgba(23,32,51,.06);
  border:1px solid var(--line);border-radius:4px;padding:1px 5px;
}}
pre{{
  font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace;
  font-size:.82em;line-height:1.6;
  background:rgba(23,32,51,.04);border:1px solid var(--line);
  border-radius:6px;padding:14px 16px;white-space:pre-wrap;word-break:break-word;
}}
a{{color:var(--blue);text-decoration:none}}
a:hover{{text-decoration:underline}}

/* ── Shell ── */
.shell{{
  display:grid;
  grid-template-columns:280px minmax(0,1fr);
  min-height:100vh;
}}

/* ── Aside ── */
aside{{
  position:sticky;top:0;height:100vh;overflow-y:auto;
  border-right:1px solid var(--line);
  background:rgba(255,253,248,.92);
  padding:22px 18px;
  display:flex;flex-direction:column;gap:20px;
}}

/* ── Brand ── */
.brand{{display:flex;align-items:center;gap:12px;margin-bottom:4px}}
.mark{{
  width:42px;height:42px;border-radius:8px;
  background:var(--ink);color:#fff;
  font:700 16px/42px ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  text-align:center;flex-shrink:0;
  box-shadow:5px 5px 0 var(--line);
}}
.brand-text{{display:flex;flex-direction:column;gap:1px}}
.kicker{{
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.65rem;font-weight:700;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);
}}

/* ── Nav ── */
.nav{{display:flex;flex-direction:column;gap:2px}}
.nav a{{
  display:flex;align-items:center;justify-content:space-between;
  padding:6px 10px;border-radius:5px;
  font-size:.82rem;font-weight:500;color:var(--ink);
  transition:background .12s,color .12s;
}}
.nav a:hover{{background:rgba(23,32,51,.06);text-decoration:none}}
.nav a.active{{background:var(--ink);color:#fff}}
.nav a .num{{
  font-size:.7rem;font-weight:700;color:var(--muted);
  background:rgba(23,32,51,.07);border-radius:4px;
  padding:1px 5px;
}}
.nav a.active .num{{color:rgba(255,255,255,.5);background:rgba(255,255,255,.12)}}

/* ── Search ── */
.search{{
  width:100%;padding:7px 10px;
  border:1px solid var(--line);border-radius:6px;
  background:var(--paper);color:var(--ink);
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.82rem;outline:none;
}}
.search:focus{{border-color:var(--blue);box-shadow:0 0 0 3px rgba(21,71,111,.12)}}

/* ── Main ── */
main{{
  padding:34px clamp(18px,4vw,64px) 80px;
  min-width:0;
}}

/* ── Hidden (search) ── */
.hidden{{display:none!important}}

/* ── Hero ── */
.hero{{
  min-height:70vh;
  border-bottom:2px solid var(--ink);
  margin-bottom:38px;
  padding-bottom:38px;
  display:flex;flex-direction:column;justify-content:center;gap:32px;
}}
.hero-grid{{
  display:grid;
  grid-template-columns:1fr 320px;
  gap:32px;align-items:start;
}}
@media(max-width:700px){{.hero-grid{{grid-template-columns:1fr}}}}

/* ── Section head ── */
.section-head{{margin-bottom:20px}}
.section-head h2{{margin-top:0}}
.section-head p{{color:var(--muted);font-size:.95rem}}

/* ── Board ── */
.board{{
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:8px;
  padding:0;overflow:hidden;
}}

/* ── Fact ── */
.fact{{
  display:grid;grid-template-columns:128px 1fr;
  padding:9px 14px;
  border-bottom:1px solid var(--line);
  font-size:.88rem;gap:12px;align-items:baseline;
}}
.fact:last-child{{border-bottom:none}}
.fact>span:first-child{{color:var(--muted);font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:.78rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em}}

/* ── Stats ── */
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:32px}}
.stat{{background:var(--panel);padding:18px 20px}}
.stat strong{{display:block;font-size:1.9rem;font-weight:800;line-height:1;color:var(--ink);margin-bottom:4px}}
.stat span{{font-size:.78rem;color:var(--muted);font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-weight:600;text-transform:uppercase;letter-spacing:.06em}}

/* ── Decision ── */
.decision{{
  display:grid;grid-template-columns:88px 1fr;
  gap:14px;padding:14px 0;
  border-bottom:1px solid var(--line);
  align-items:start;font-size:.9rem;
}}
.decision:last-child{{border-bottom:none}}
.id{{
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.72rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;
  border:1.5px solid currentColor;border-radius:5px;
  padding:3px 7px;display:inline-block;align-self:start;
}}

/* ── Rule ── */
.rule-group{{margin-bottom:28px}}
.rule-group-head{{
  display:flex;align-items:center;gap:10px;
  padding:8px 0 10px;border-bottom:2px solid var(--ink);
  margin-bottom:0;
}}
.rule-group-head h3{{margin:0;font-size:.88rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}}
.rule{{
  display:grid;grid-template-columns:152px 1fr 180px;
  gap:12px;padding:10px 0;
  border-bottom:1px solid var(--line);
  align-items:start;font-size:.88rem;
}}
.rule:last-child{{border-bottom:none}}
.rule-id{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.group-code{{
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.65rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
  background:var(--ink);color:#fff;border-radius:3px;padding:2px 5px;
  white-space:nowrap;
}}
.rule small{{color:var(--muted);font-size:.78rem}}

/* ── Tags / Pills ── */
.tags{{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}}
.tags span,.pill{{
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.7rem;font-weight:600;letter-spacing:.04em;
  border:1px solid var(--line);border-radius:4px;
  padding:2px 7px;color:var(--muted);background:rgba(23,32,51,.04);
  display:inline-block;
}}

/* ── Filters ── */
.filters{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}}
.filter-button{{
  font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  padding:5px 12px;border-radius:5px;border:1px solid var(--line);
  background:transparent;color:var(--muted);cursor:pointer;
  transition:all .12s;
}}
.filter-button:hover{{background:rgba(23,32,51,.06)}}
.filter-button.active{{background:var(--ink);color:#fff;border-color:var(--ink)}}

/* ── Callout ── */
.callout{{
  background:rgba(21,71,111,.06);border:1px solid rgba(21,71,111,.2);
  border-left:3px solid var(--blue);border-radius:6px;
  padding:12px 16px;margin:14px 0;font-size:.88rem;
}}
.callout p:last-child{{margin-bottom:0}}

section{{margin-bottom:52px}}
</style>
</head>
<body>
<div class="shell">

<!-- ═══════════════════════════ ASIDE ═══════════════════════════ -->
<aside>
  <div class="brand">
    <div class="mark">{_e(initials)}</div>
    <div class="brand-text">
      <span class="kicker">Living Spec</span>
      <strong>{_e(project_name)}</strong>
    </div>
  </div>

  <nav class="nav">
{nav_html}
  </nav>

  <input id="search" class="search" type="search" placeholder="search spec..." autocomplete="off">
</aside>

<!-- ═══════════════════════════ MAIN ═══════════════════════════ -->
<main>

<!-- ── 00 Overview ── -->
<section id="overview" class="hero">
  <div class="hero-grid">
    <div>
      {_pill("v1.0", "color:var(--blue);border-color:color-mix(in srgb,var(--blue) 35%,var(--line));font-size:.72rem;font-weight:700;letter-spacing:.05em;margin-bottom:14px;display:inline-block")}
      <h1>Harness &mdash; {_e(project_name)}</h1>
      <p style="color:var(--muted);font-size:1.05rem;max-width:52ch">
        Tri-center orchestration spec for <strong>{_e(project_name)}</strong>.
        Routes tasks across Codex, Claude, and Antigravity based on keyword signals,
        live quota, and observed token cost.
      </p>
    </div>
    <div class="board">
      {_fact("Language",   f"<strong>{_e(language)}</strong>")}
      {_fact("Framework",  f"<strong>{_e(framework)}</strong>" if framework else "<span style='color:var(--muted)'>—</span>")}
      {_fact("Entry point", f"<code>{_e(str(entry_points[0]))}</code>" if entry_points else "<span style='color:var(--muted)'>—</span>")}
      {_fact("Agents detected", f"<strong>{agent_count}</strong>")}
      {_fact("Generated",  _e(today))}
    </div>
  </div>

  <div class="stats">
    <div class="stat"><strong>{kw_count}</strong><span>Keywords</span></div>
    <div class="stat"><strong>{agent_count}</strong><span>Agents</span></div>
    <div class="stat"><strong>{feat_count}</strong><span>Features</span></div>
  </div>
</section>

<!-- ── 01 Profile ── -->
<section id="profile">
  <div class="section-head">
    <span class="kicker">Stack</span>
    <h2>Project profile</h2>
  </div>
  <div class="board">
    {_fact("Language",    f"<strong>{_e(language)}</strong>")}
    {_fact("Framework",   f"<strong>{_e(framework)}</strong>" if framework else "<span style='color:var(--muted)'>—</span>")}
    {_fact("Secondary",   _e(sec_lang_str))}
    {_fact("Config file", f"<code>{_e(config_file)}</code>" if config_file else "<span style='color:var(--muted)'>—</span>")}
    {ep_facts}
  </div>
</section>

<!-- ── 02 Routing ── -->
<section id="routing">
  <div class="section-head">
    <span class="kicker">Routing policy</span>
    <h2>Tri-center routing</h2>
    <p>The router reads task keywords, live quota, and observed token cost to pick the optimal center. Every task passes through <strong>auto</strong> first.</p>
  </div>

  <div style="margin-bottom:28px">
    <div class="decision">
      <span class="id" style="color:var(--blue);border-color:color-mix(in srgb,var(--blue) 35%,var(--line))">auto</span>
      <div>{_tags("auto")}<p style="margin:6px 0 0">Always the entry point. Reads task keywords and dispatches to the optimal center below.</p></div>
    </div>
    <div class="decision">
      <span class="id" style="color:var(--amber);border-color:color-mix(in srgb,var(--amber) 35%,var(--line))">codex</span>
      <div>{_tags("codex")}<p style="margin:6px 0 0">Heavy codegen, repo-wide refactor, long multi-file edits. Triggered by coding keywords.</p></div>
    </div>
    <div class="decision">
      <span class="id" style="color:var(--green);border-color:color-mix(in srgb,var(--green) 35%,var(--line))">claude</span>
      <div>{_tags("claude")}<p style="margin:6px 0 0">Compact review, quick fixes, debugging, analysis. Low-token implementation and review worker.</p></div>
    </div>
    <div class="decision">
      <span class="id" style="color:var(--muted);border-color:var(--line)">antigravity</span>
      <div>{_tags("antigravity")}<p style="margin:6px 0 0">Broad research, large-context reads, architecture planning. Triggered by research keywords.</p></div>
    </div>
  </div>

  <div class="filters">
    <button class="filter-button active" data-filter="ALL">ALL</button>
    <button class="filter-button" data-filter="RESEARCH">RESEARCH</button>
    <button class="filter-button" data-filter="CODING">CODING</button>
  </div>

  <div class="rule-group">
    <div class="rule-group-head"><h3>Routing keywords</h3></div>
    {_kw_rules(research_kws, "RESEARCH")}
    {_kw_rules(coding_kws,   "CODING")}
  </div>
</section>

<!-- ── 03 Agents ── -->
<section id="agents">
  <div class="section-head">
    <span class="kicker">Agents detected</span>
    <h2>Agent configuration</h2>
  </div>
  <div class="rule-group">
    <div class="rule-group-head"><h3>Detected configs</h3></div>
    {_agent_rules()}
  </div>
  <div class="callout">
    <p>Copy <code>.harness/mcp.json</code> into your agent&rsquo;s MCP settings to connect to the Harness server at <code>{_e(scripts)}</code>.</p>
  </div>
</section>

<!-- ── 04 Features ── -->
<section id="features">
  <div class="section-head">
    <span class="kicker">Default-fail</span>
    <h2>Features</h2>
    <p>All features start not-run. Each must earn a pass verdict.</p>
  </div>
  <div class="rule-group">
    <div class="rule-group-head"><h3>Feature registry</h3></div>
    {_feature_rules()}
  </div>
</section>

<!-- ── 05 Context ── -->
<section id="context">
  <div class="section-head">
    <span class="kicker">RAG + memory</span>
    <h2>Context economy</h2>
    <p>Use context packs to compress repo content before any cloud reasoning step.</p>
  </div>
  {mcp_decisions_html}
</section>

<!-- ── 06 Commands ── -->
<section id="commands">
  <div class="section-head">
    <span class="kicker">CLI</span>
    <h2>Key commands</h2>
  </div>
  <div class="board">
    <div style="padding:16px 18px">
<pre># Route a task to the optimal center
harness route "&lt;task description&gt;"

# Build compact context before any cloud call
harness context "&lt;query&gt;"           # BM25 hybrid
harness context semantic "&lt;query&gt;"  # semantic (requires embed model)

# Health check — MCP, retrieval, quota, memory
harness health

# Build or rebuild the semantic index
harness index

# Suggest next bounded self-growth action
harness autopilot

# Status and data paths for this project
harness status</pre>
    </div>
  </div>
</section>

<!-- ── 07 Layout ── -->
<section id="layout">
  <div class="section-head">
    <span class="kicker">File layout</span>
    <h2>Data layout</h2>
  </div>
  <div class="board">
    {_fact(".harness/state.json",        "Center preferences, quotas, routing policy")}
    {_fact(".harness/project.json",      "Language, framework, detected agents, analyzed_at")}
    {_fact(".harness/index.json",        "BM25 search index")}
    {_fact(".harness/memory.jsonl",      "Operational memories (content-hash deduped)")}
    {_fact(".harness/mcp.json",          "MCP server config — paste into Claude Desktop")}
    {_fact(".harness/hooks.json",        "Lifecycle hooks: before_tool, after_tool, on_error")}
    {_fact(".harness/handoffs/",         "Structured center-to-center handoff files")}
    {_fact(".harness/context_packs/",    "Pre-built compact context for cloud calls")}
    {_fact(".harness/trajectories/",     "Session step traces + failure classification")}
    {_fact(".harness/telemetry/",        "Chain IDs, span durations, token counts")}
    {_fact(".harness/growth/",           "Routing evidence + experiment queue")}
    {_fact("HARNESS.md",                 "Agent-readable guidelines + project conventions")}
    {_fact("HARNESS.html",               "This file")}
  </div>
</section>

{workflow_section_html}
{agent_sections_html}

<div style="border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:.8rem;font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  Harness &middot; {_e(project_name)} &middot; {today} &middot; scripts: {_e(scripts)}
</div>

</main>
</div>

<script>
const search = document.querySelector('#search');
const blocks = [...document.querySelectorAll('section, .rule, .card, .decision')];
const navLinks = [...document.querySelectorAll('.nav a')];
const filterButtons = [...document.querySelectorAll('.filter-button')];
const normalize = value => value.toLowerCase().replace(/[-/]+/g, ' ');
search.addEventListener('input', () => {{
  const q = normalize(search.value.trim());
  blocks.forEach(block => block.classList.toggle('hidden', q && !normalize(block.textContent).includes(q)));
}});
filterButtons.forEach(button => button.addEventListener('click', () => {{
  filterButtons.forEach(item => item.classList.toggle('active', item === button));
  const filter = button.dataset.filter;
  document.querySelectorAll('[data-groups]').forEach(el => {{
    const groups = (el.dataset.groups || '').split(' ');
    el.classList.toggle('hidden', filter !== 'ALL' && !groups.includes(filter));
  }});
}}));
const observer = new IntersectionObserver(entries => {{
  entries.forEach(entry => {{
    if (!entry.isIntersecting) return;
    navLinks.forEach(link => link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id));
  }});
}}, {{ rootMargin: '-40% 0px -55% 0px' }});
navLinks.forEach(link => {{
  const target = document.querySelector(link.getAttribute('href'));
  if (target) observer.observe(target);
}});
</script>
</body>
</html>
"""


