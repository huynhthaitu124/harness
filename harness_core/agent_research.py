"""Agent-driven codebase research for HARNESS.html project-specific sections.

Detects available agent CLIs (claude, codex, antigravity, local Ollama) and
invokes the selected agent to generate structured project-specific content
beyond the standard 8 base sections in HARNESS.html.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

_EMBED_HINTS = ("embed", "nomic", "mxbai", "bge", "e5", "minilm", "gte", "jina", "all-mini")


# ── Agent detection ────────────────────────────────────────────────────────────

def _ollama_running() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
            return True
    except Exception:
        return False


def _ollama_chat_models() -> list[str]:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            data = json.loads(resp.read())
        return [
            m["name"] for m in data.get("models", [])
            if not any(h in m["name"].lower() for h in _EMBED_HINTS)
        ]
    except Exception:
        return []


def _claude_authed() -> bool:
    """Return True if claude CLI has valid auth configured."""
    try:
        r = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        out = (r.stdout + r.stderr).lower()
        return "logged in" in out or "authenticated" in out or r.returncode == 0
    except Exception:
        return False


def detect_agent_clis() -> list[dict[str, Any]]:
    """Detect available agent CLIs + local Ollama chat models.

    Each entry:
      name          identifier used to invoke  (e.g. "claude", "ollama:llama3.2")
      label         human-readable display string
      available     bool — installed AND ready to use (auth ok, model pulled)
      installed     bool — binary / runtime exists on this machine
      authed        bool — auth credentials configured (Claude / Codex)
      detail        short status string for TUI display
      model         only set for Ollama model entries
      install_how   "npm" | "brew" | "url" | "ollama_pull" | None
      install_pkg   package/formula name to install
      auth_cmd      list[str] command to run for auth, or None
      auth_url      URL to open for auth, or None
      auth_note     extra plain-text instruction shown after install
    """
    agents: list[dict[str, Any]] = []
    npm_ok    = bool(shutil.which("npm"))
    brew_ok   = bool(shutil.which("brew"))

    # ── Claude Code CLI ────────────────────────────────────────────────────────
    claude_path = shutil.which("claude")
    claude_inst = bool(claude_path)
    claude_auth = _claude_authed() if claude_inst else False
    agents.append({
        "name":        "claude",
        "label":       "Claude Code",
        "available":   claude_inst and claude_auth,
        "installed":   claude_inst,
        "authed":      claude_auth,
        "detail":      (claude_path if claude_inst and claude_auth
                        else ("installed — needs login" if claude_inst
                              else ("npm i -g @anthropic-ai/claude-code" if npm_ok
                                    else "requires Node/npm"))),
        "model":       None,
        "install_how": "npm" if npm_ok else None,
        "install_pkg": "@anthropic-ai/claude-code",
        "auth_cmd":      ["claude", "auth", "login"],
        "auth_url":      "https://claude.ai/settings/cli",
        "auth_note":     "Opens your browser — sign in with your Anthropic account.",
        "docs_url":      "https://docs.anthropic.com/claude-code",
        "install_steps": [
            "npm install -g @anthropic-ai/claude-code",
            "claude auth login  # opens browser — sign in with Anthropic",
            "claude --version  # verify",
        ],
    })

    # ── Codex CLI ─────────────────────────────────────────────────────────────
    codex_path = shutil.which("codex")
    codex_inst = bool(codex_path)
    # Codex auth = OPENAI_API_KEY is set
    import os as _os
    codex_auth = bool(_os.environ.get("OPENAI_API_KEY"))
    agents.append({
        "name":        "codex",
        "label":       "Codex (OpenAI)",
        "available":   codex_inst and codex_auth,
        "installed":   codex_inst,
        "authed":      codex_auth,
        "detail":      (codex_path if codex_inst and codex_auth
                        else ("installed — set OPENAI_API_KEY" if codex_inst
                              else ("npm i -g @openai/codex" if npm_ok
                                    else "requires Node/npm"))),
        "model":       None,
        "install_how": "npm" if npm_ok else None,
        "install_pkg": "@openai/codex",
        "auth_cmd":      None,
        "auth_url":      "https://platform.openai.com/api-keys",
        "auth_note":     "Create an API key at platform.openai.com, then add to your shell:\n"
                         "export OPENAI_API_KEY=sk-...\n"
                         "Add to ~/.zshrc or ~/.bashrc to persist across sessions.",
        "docs_url":      "https://github.com/openai/codex-cli",
        "install_steps": [
            "npm install -g @openai/codex",
            "# Get API key at https://platform.openai.com/api-keys",
            "export OPENAI_API_KEY=sk-...  # add to ~/.zshrc to persist",
            "codex --version  # verify",
        ],
    })

    # ── Antigravity CLI ───────────────────────────────────────────────────────
    ag_path  = shutil.which("antigravity")
    ag_inst  = bool(ag_path)
    ag_auth  = False
    if ag_inst:
        try:
            _r = subprocess.run(
                ["antigravity", "auth", "status"],
                capture_output=True, text=True, timeout=8,
            )
            ag_auth = _r.returncode == 0 or "logged" in (_r.stdout + _r.stderr).lower()
        except Exception:
            ag_auth = False  # require explicit auth confirmation
    ag_version = ""
    if ag_inst:
        try:
            _vr = subprocess.run(
                ["antigravity", "--version"], capture_output=True, text=True, timeout=5,
            )
            ag_version = (_vr.stdout + _vr.stderr).strip().split("\n")[0][:40]
        except Exception:
            pass
    agents.append({
        "name":          "antigravity",
        "label":         "Antigravity CLI",
        "available":     ag_inst and ag_auth,
        "installed":     ag_inst,
        "authed":        ag_auth,
        "detail":        (ag_version or ag_path or "ready") if ag_inst
                         else "download from antigravity.google",
        "model":         None,
        "install_how":   "url",
        "install_pkg":   None,
        "auth_cmd":      ["antigravity", "auth", "login"],
        "auth_url":      "https://antigravity.google/download#antigravity-cli",
        "auth_note":     "Sign in with your Google account to authorise Antigravity CLI.",
        "docs_url":      "https://antigravity.google/download#antigravity-cli",
        "install_steps": [
            "# Download from https://antigravity.google/download#antigravity-cli",
            "antigravity auth login  # opens browser — sign in with Google",
            "antigravity --version  # verify",
        ],
    })

    # ── Ollama (platform + models) ─────────────────────────────────────────────
    ollama_path    = shutil.which("ollama")
    ollama_inst    = bool(ollama_path)
    ollama_running = _ollama_running() if ollama_inst else False
    chat_models    = _ollama_chat_models() if ollama_running else []

    if not ollama_inst:
        # Offer to install Ollama itself — it will let the user pull a model next
        agents.append({
            "name":        "__install_ollama__",
            "label":       "Local model (Ollama — not installed)",
            "available":   False,
            "installed":   False,
            "authed":      True,
            "detail":      "brew install ollama" if brew_ok else "download from ollama.com",
            "model":       None,
            "install_how": "brew" if brew_ok else "url",
            "install_pkg": "ollama",
            "auth_cmd":    None,
            "auth_url":    "https://ollama.com/download",
            "auth_note":   "",
        })
    elif not chat_models:
        # Ollama installed but no chat models — offer to pull one
        agents.append({
            "name":        "__pull_ollama_model__",
            "label":       "Local model (Ollama — no models pulled yet)",
            "available":   False,
            "installed":   True,
            "authed":      True,
            "detail":      "pull a model with: ollama pull qwen3:8b",
            "model":       None,
            "install_how": "ollama_pull",
            "install_pkg": None,
            "auth_cmd":    None,
            "auth_url":    None,
            "auth_note":   "",
        })
    else:
        for m in chat_models[:4]:
            agents.append({
                "name":        f"ollama:{m}",
                "label":       f"Local — {m}",
                "available":   True,
                "installed":   True,
                "authed":      True,
                "detail":      "offline · no API cost",
                "model":       m,
                "install_how": None,
                "install_pkg": None,
                "auth_cmd":    None,
                "auth_url":    None,
                "auth_note":   "",
            })

    return agents


# ── Install / auth helpers ─────────────────────────────────────────────────────

def install_agent_cli(agent: dict[str, Any]) -> bool:
    """Install the agent CLI. Returns True if successful."""
    how = agent.get("install_how")
    pkg = agent.get("install_pkg", "")

    if how == "npm":
        cmd = ["npm", "install", "-g", pkg]
    elif how == "brew":
        cmd = ["brew", "install", pkg]
    elif how == "url":
        # Can't install automatically — open browser
        url = agent.get("auth_url") or "https://ollama.com/download"
        try:
            subprocess.run(["open", url], check=False)
        except Exception:
            pass
        return False
    elif how == "ollama_pull":
        # Handled separately via _pick_ollama_model
        return False
    else:
        return False

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        import sys as _sys
        for line in proc.stdout or []:
            _sys.stdout.write(f"    {line}")
            _sys.stdout.flush()
        proc.wait(timeout=300)
        print()
        return proc.returncode == 0
    except Exception as exc:
        print(f"    install failed: {exc}")
        return False


def run_agent_auth(agent: dict[str, Any]) -> bool:
    """Run the auth flow for an agent. Returns True when auth appears complete."""
    import sys as _sys

    auth_cmd  = agent.get("auth_cmd")
    auth_url  = agent.get("auth_url")
    auth_note = agent.get("auth_note", "")

    if auth_note:
        for line in auth_note.splitlines():
            _sys.stdout.write(f"  · {line}\n")
        _sys.stdout.flush()

    if auth_url and not auth_cmd:
        # Can't do it programmatically — open browser and tell user
        try:
            subprocess.run(["open", auth_url], check=False)
        except Exception:
            pass
        _sys.stdout.write(f"  → opened {auth_url}\n")
        _sys.stdout.flush()
        input("  Press Enter once you've completed authentication... ")
        return True

    if auth_cmd:
        # Run auth command interactively (don't capture — it needs TTY for browser flow)
        try:
            subprocess.run(auth_cmd, check=False)
            return True
        except Exception as exc:
            _sys.stdout.write(f"  ! auth command failed: {exc}\n")
            return False

    return True  # no auth needed


# ── Research prompt ────────────────────────────────────────────────────────────

_JSON_SCHEMA = """{
  "sections": [
    {
      "id": "architecture",
      "title": "Architecture",
      "kicker": "How it's built",
      "type": "facts",
      "summary": "2-3 sentence overview of the design",
      "facts": [
        {"label": "Pattern", "value": "describe the main design pattern"},
        {"label": "Layers",  "value": "describe main layers or subsystems"}
      ],
      "rules": []
    },
    {
      "id": "key_modules",
      "title": "Key modules",
      "kicker": "Core files",
      "type": "rules",
      "summary": "The most important files to understand",
      "facts": [],
      "rules": [
        {"id": "path/to/file.py", "content": "what this file does", "note": "when to edit it"}
      ]
    },
    {
      "id": "conventions",
      "title": "Conventions",
      "kicker": "How we code",
      "type": "rules",
      "summary": "Key coding patterns and style rules",
      "facts": [],
      "rules": [
        {"id": "CONV-001", "content": "describe the convention", "note": "why it matters"}
      ]
    },
    {
      "id": "workflow",
      "title": "Build & test",
      "kicker": "Running the project",
      "type": "facts",
      "summary": "How to build, test, and run the project",
      "facts": [
        {"label": "Install", "value": "install command"},
        {"label": "Test",    "value": "test command"},
        {"label": "Run",     "value": "run command"}
      ],
      "rules": []
    },
    {
      "id": "skills",
      "title": "Agent skills",
      "kicker": "Automation",
      "type": "rules",
      "summary": "Automated skills and workflows defined in .agents/ for this project. Leave empty array if none found.",
      "facts": [],
      "rules": [
        {"id": "skill-name", "content": "what this skill does and when to use it", "note": "invoke with: /skill-name or harness run <skill>"}
      ]
    },
    {
      "id": "specifications",
      "title": "Specifications",
      "kicker": "Requirements & design",
      "type": "rules",
      "summary": "Key specs, requirements, and design decisions found in docs/specs directories. Leave empty array if none found.",
      "facts": [],
      "rules": [
        {"id": "path/to/spec.md", "content": "what this spec defines — scope and key decisions", "note": "status: draft / approved / superseded"}
      ]
    },
    {
      "id": "documentation",
      "title": "Documentation",
      "kicker": "Project docs",
      "type": "rules",
      "summary": "Existing project documentation files and what each covers. Leave empty array if none found.",
      "facts": [],
      "rules": [
        {"id": "path/to/doc.md", "content": "what this document covers and who should read it", "note": "audience: dev / ops / user / all"}
      ]
    },
    {
      "id": "open_questions",
      "title": "Open questions",
      "kicker": "Tech debt & unknowns",
      "type": "rules",
      "summary": "Areas needing attention or clarification",
      "facts": [],
      "rules": [
        {"id": "Q-001", "content": "describe the question or gap", "note": "priority: high/medium/low"}
      ]
    }
  ]
}"""


def _build_research_prompt(
    root: Path,
    analysis: dict[str, Any],
    context: str,
    doc_context: str = "",
) -> str:
    project_name = analysis.get("project_name", root.name)
    language     = analysis.get("language", "unknown")
    framework    = analysis.get("framework", "") or "—"
    entry_points = analysis.get("entry_points") or []
    agents       = analysis.get("agents") or []

    ep_str    = ", ".join(str(e) for e in entry_points[:3]) or "—"
    agent_str = ", ".join(a.get("agent", str(a)) if isinstance(a, dict) else str(a) for a in agents[:4]) or "none"

    doc_block = (
        f"\nHere is content from agent skill definitions, specifications, and documentation files"
        f" — use these to fill the skills, specifications, and documentation sections:\n\n"
        f"{doc_context}\n"
    ) if doc_context.strip() else ""

    return (
        f"Please help document the {project_name} project for its development team.\n"
        f"\n"
        f"Project details:\n"
        f"- Location: {root}\n"
        f"- Language: {language}, Framework: {framework}\n"
        f"- Entry points: {ep_str}\n"
        f"- Agent configs: {agent_str}\n"
        f"\n"
        f"Here is the content of the key source files:\n"
        f"\n"
        f"{context}\n"
        f"{doc_block}\n"
        f"Based on ALL the files above (source code, skills, specs, docs), fill in this JSON\n"
        f"documentation template with accurate, specific information about this project.\n"
        f"Replace placeholder text with real findings from the files.\n"
        f"For sections where no relevant files were found (skills, specifications, documentation),\n"
        f"set rules to an empty array [] and write a brief summary saying none were found.\n"
        f"Keep each 'id' field unchanged. Respond with the completed JSON only:\n"
        f"\n"
        f"{_JSON_SCHEMA}\n"
    )


# ── Agent invocation ───────────────────────────────────────────────────────────

def run_agent_research(
    root: Path,
    agent_name: str,
    analysis: dict[str, Any],
) -> dict[str, Any] | None:
    """Run agent-driven codebase research. Returns parsed dict with 'sections' or None."""
    from harness_core.project_analyzer import (
        build_analysis_context,
        build_doc_context,
        extract_doc_files,
        extract_key_files,
    )

    key_files   = extract_key_files(root)
    context     = build_analysis_context(root, key_files)
    doc_files   = extract_doc_files(root)
    doc_context = build_doc_context(root, doc_files)
    prompt      = _build_research_prompt(root, analysis, context, doc_context)

    raw: str | None = None
    if agent_name == "claude":
        raw = _invoke_claude(root, prompt)
    elif agent_name == "codex":
        raw = _invoke_codex(root, prompt)
    elif agent_name == "antigravity":
        raw = _invoke_antigravity(root, prompt)
    elif agent_name.startswith("ollama:"):
        model = agent_name[len("ollama:"):]
        raw = _invoke_ollama(model, prompt)

    if not raw:
        return None

    parsed = _parse_research_json(raw, agent_name)
    if parsed is None:
        # Show first 200 chars of raw to help debug
        import sys as _sys
        preview = raw[:200].replace("\n", " ") if len(raw) > 200 else raw.replace("\n", " ")
        _sys.stdout.write(f"  ! JSON parse failed. Agent output preview: {preview!r}\n")
        _sys.stdout.flush()
    return parsed


def _stream_subprocess(
    cmd: list[str],
    prompt: str,
    root: Path,
    timeout: int = 300,
    show_stderr: bool = True,
) -> str | None:
    """Run a CLI command, streaming stdout/stderr to terminal while capturing stdout.

    Returns the full stdout content as a string, or None on failure.
    Output is shown indented under the harness output so the user can follow along.
    """
    import sys as _sys
    import threading

    stdout_chunks: list[str] = []

    def _reader(pipe, capture: bool) -> None:
        try:
            for raw_line in pipe:
                _sys.stdout.write(f"    {raw_line}" if not raw_line.startswith("    ") else raw_line)
                _sys.stdout.flush()
                if capture:
                    stdout_chunks.append(raw_line)
        except Exception:
            pass

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if show_stderr else subprocess.DEVNULL,
            text=True,
            cwd=str(root),
            bufsize=1,
        )

        t_out = threading.Thread(target=_reader, args=(proc.stdout, True), daemon=True)
        t_out.start()
        if show_stderr and proc.stderr:
            t_err = threading.Thread(target=_reader, args=(proc.stderr, False), daemon=True)
            t_err.start()
        else:
            t_err = None

        # Send prompt and close stdin so the process can proceed
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except BrokenPipeError:
            pass

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            print()
            return None

        t_out.join(timeout=10)
        if t_err:
            t_err.join(timeout=5)

        print()  # newline after streaming output

        output = "".join(stdout_chunks).strip()
        return output if output else None

    except FileNotFoundError:
        return None
    except Exception:
        return None


def _invoke_claude(root: Path, prompt: str) -> str | None:
    """Invoke claude CLI non-interactively, streaming output to terminal."""
    import sys as _sys

    print()
    _sys.stdout.write("  ┌─ claude output ─────────────────────────────────────────\n")
    _sys.stdout.flush()

    # Try --print then -p as fallback
    for flag in ("--print", "-p"):
        result = _stream_subprocess(["claude", flag], prompt, root, timeout=300)
        if result:
            _sys.stdout.write("  └────────────────────────────────────────────────────────\n")
            _sys.stdout.flush()
            return result

    _sys.stdout.write("  └─ no output received ──────────────────────────────────\n")
    _sys.stdout.flush()
    return None


def _invoke_codex(root: Path, prompt: str) -> str | None:
    """Invoke codex CLI non-interactively, streaming output to terminal."""
    import sys as _sys

    print()
    _sys.stdout.write("  ┌─ codex output ──────────────────────────────────────────\n")
    _sys.stdout.flush()

    result = _stream_subprocess(["codex", "--quiet", prompt], prompt, root, timeout=300)

    _sys.stdout.write("  └────────────────────────────────────────────────────────\n")
    _sys.stdout.flush()
    return result


def _invoke_antigravity(root: Path, prompt: str) -> str | None:
    """Invoke antigravity CLI, streaming output to terminal."""
    import sys as _sys

    print()
    _sys.stdout.write("  ┌─ antigravity output ────────────────────────────────────\n")
    _sys.stdout.flush()

    result = _stream_subprocess(["antigravity", "ask", prompt], prompt, root, timeout=300)

    _sys.stdout.write("  └────────────────────────────────────────────────────────\n")
    _sys.stdout.flush()
    return result


def _invoke_ollama(model: str, prompt: str, host: str = "http://localhost:11434") -> str | None:
    """Invoke an Ollama model via the streaming generate API, showing output in real-time."""
    import sys as _sys

    payload = json.dumps({
        "model":   model,
        "prompt":  prompt,
        "stream":  True,
        "options": {"temperature": 0.1, "num_predict": 4096},
    }).encode("utf-8")

    print()
    _sys.stdout.write(f"  ┌─ {model} output ──────────────────────────────────────\n")
    _sys.stdout.flush()

    chunks: list[str] = []
    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            current_line = ""
            for raw in resp:
                try:
                    token = json.loads(raw).get("response", "")
                except Exception:
                    continue
                chunks.append(token)
                current_line += token
                # Stream line by line so terminal doesn't flicker
                while "\n" in current_line:
                    line, current_line = current_line.split("\n", 1)
                    _sys.stdout.write(f"    {line}\n")
                    _sys.stdout.flush()
            if current_line:
                _sys.stdout.write(f"    {current_line}\n")
                _sys.stdout.flush()

        _sys.stdout.write("  └────────────────────────────────────────────────────────\n")
        _sys.stdout.flush()
        print()
        return "".join(chunks).strip() or None

    except Exception as exc:
        _sys.stdout.write(f"  └─ error: {exc}\n")
        _sys.stdout.flush()
        return None


def _parse_research_json(raw: str, agent_name: str) -> dict[str, Any] | None:
    """Extract JSON from raw agent output. Returns {agent, sections} or None."""
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        first_fence = next((i for i, l in enumerate(lines) if l.startswith("```")), 0)
        end_fence   = next(
            (i for i, l in enumerate(lines[first_fence + 1:], first_fence + 1) if l.strip() == "```"),
            len(lines),
        )
        text = "\n".join(lines[first_fence + 1 : end_fence]).strip()

    def _try_parse(s: str) -> dict[str, Any] | None:
        try:
            data = json.loads(s)
            if "sections" in data and isinstance(data["sections"], list):
                return {"agent": agent_name, "sections": data["sections"]}
        except json.JSONDecodeError:
            pass
        return None

    result = _try_parse(text)
    if result:
        return result

    # Try to extract JSON object from within a larger text blob
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        result = _try_parse(text[start:end])
        if result:
            return result

    return None


# ── Workflow research ─────────────────────────────────────────────────────────

_WORKFLOW_SCHEMA = """{
  "ticket_system": "openproject | jira | linear | github | notion | none",
  "ticket_url": "base URL of the ticket tracker (e.g. https://op.example.com), or empty string",
  "base_branch": "branch agents checkout before starting work (e.g. development, main, master)",
  "branch_pattern": "naming pattern for new branches (e.g. bug/<id> | feat/<id>-<slug>)",
  "context_files": ["HARNESS.md", "other docs agents should always read before starting a ticket"],
  "build_cmd": "command that verifies the build passes (e.g. msbuild PAGSWebRole /t:Build, npm test, pytest, dotnet build)",
  "critical_rules": [
    "A hard rule agents must ALWAYS follow on this project",
    "Another critical rule — add as many as needed"
  ]
}"""


def _gather_git_context(root: Path) -> str:
    """Collect git log, branch names, and CI config snippets for workflow inference."""
    def _run(cmd: list[str]) -> str:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), timeout=15)
            return r.stdout.strip()
        except Exception:
            return ""

    parts: list[str] = []

    log = _run(["git", "log", "--oneline", "-80"])
    if log:
        parts.append("=== Recent commits (last 80) ===\n" + log)

    branches = _run(["git", "branch", "-a"])
    if branches:
        parts.append("\n=== All branches ===\n" + branches)

    # CI/build files — first 40 lines each
    import glob as _glob
    ci_patterns = [
        ".github/workflows/*.yml", ".github/workflows/*.yaml",
        ".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml",
        "azure-pipelines.yml", ".travis.yml", "Makefile",
    ]
    ci_found: list[str] = []
    for pat in ci_patterns:
        ci_found.extend(_glob.glob(str(root / pat)))

    for fpath in ci_found[:5]:
        rel = fpath[len(str(root)) + 1:]
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
            snippet = "\n".join(content.splitlines()[:40])
            parts.append(f"\n=== {rel} (first 40 lines) ===\n{snippet}")
        except Exception:
            parts.append(f"\n=== {rel} (unreadable) ===")

    return "\n".join(parts)


def _build_workflow_prompt(root: Path, analysis: dict[str, Any], git_ctx: str) -> str:
    project_name = analysis.get("project_name", root.name)
    language     = analysis.get("language", "unknown")
    framework    = analysis.get("framework", "") or "—"

    return (
        f"Please analyse the {project_name} project and fill in a workflow configuration JSON.\n"
        f"\n"
        f"Project: {project_name} | Language: {language} | Framework: {framework}\n"
        f"Location: {root}\n"
        f"\n"
        f"Use the git history and branch names below to infer:\n"
        f"- Which ticket system is used (look for ticket refs like OP-123, PROJ-456, #123, etc.)\n"
        f"- The ticket tracker URL if visible in commit messages or branch names\n"
        f"- The base branch agents should work from (look at what branches are merged into)\n"
        f"- The branch naming pattern (e.g. bug/OP-123, feat/123-title)\n"
        f"- What build or test command to run to verify changes (look at CI config, Makefiles, package.json)\n"
        f"- Any critical rules the team clearly follows (from branch prefixes, commit patterns, CI gates)\n"
        f"\n"
        f"--- Git context ---\n"
        f"{git_ctx or '(no git history found)'}\n"
        f"---\n"
        f"\n"
        f"Fill in this JSON template with your findings. If you cannot determine a field, use an empty string.\n"
        f"Respond with only the completed JSON:\n"
        f"\n"
        f"{_WORKFLOW_SCHEMA}\n"
    )


def _parse_workflow_json(raw: str) -> dict[str, Any] | None:
    """Extract and validate a workflow dict from raw agent output."""
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        first = next((i for i, l in enumerate(lines) if l.startswith("```")), 0)
        end   = next(
            (i for i, l in enumerate(lines[first + 1:], first + 1) if l.strip() == "```"),
            len(lines),
        )
        text = "\n".join(lines[first + 1 : end]).strip()

    def _try(s: str) -> dict[str, Any] | None:
        try:
            data = json.loads(s)
            # Must have at least one of the expected keys
            if any(k in data for k in ("ticket_system", "base_branch", "build_cmd", "critical_rules")):
                return data
        except json.JSONDecodeError:
            pass
        return None

    result = _try(text)
    if result:
        return result

    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        return _try(text[start:end])

    return None


def research_workflow(
    root: Path,
    agent_name: str,
    analysis: dict[str, Any],
) -> "dict[str, Any] | None":
    """Use the selected agent to infer the project's ticket workflow from git history.

    Returns a full workflow dict (via answers_to_workflow) or None on failure.
    """
    import sys as _sys
    from harness_core.workflow_steps import answers_to_workflow

    _sys.stdout.write("  Gathering git context for workflow inference...\n")
    _sys.stdout.flush()
    git_ctx = _gather_git_context(root)

    prompt = _build_workflow_prompt(root, analysis, git_ctx)

    raw: str | None = None
    if agent_name == "claude":
        raw = _invoke_claude(root, prompt)
    elif agent_name == "codex":
        raw = _invoke_codex(root, prompt)
    elif agent_name == "antigravity":
        raw = _invoke_antigravity(root, prompt)
    elif agent_name.startswith("ollama:"):
        raw = _invoke_ollama(agent_name[len("ollama:"):], prompt)

    if not raw:
        return None

    parsed = _parse_workflow_json(raw)
    if parsed is None:
        preview = raw[:200].replace("\n", " ")
        _sys.stdout.write(f"  ! workflow JSON parse failed. Preview: {preview!r}\n")
        _sys.stdout.flush()
        return None

    # Convert agent dict → full workflow with patched steps
    grill_answers = {
        "wf_ticket_system":  parsed.get("ticket_system", ""),
        "wf_ticket_url":     parsed.get("ticket_url", ""),
        "wf_base_branch":    parsed.get("base_branch", ""),
        "wf_branch_pattern": parsed.get("branch_pattern", ""),
        "wf_context_files":  ", ".join(parsed.get("context_files", [])),
        "wf_build_cmd":      parsed.get("build_cmd", ""),
        "wf_critical_rules": "\\n".join(parsed.get("critical_rules", [])),
    }
    return answers_to_workflow(grill_answers)


def research_workflow_from_text(
    root: Path,
    agent_name: str,
    user_text: str,
    base_workflow: "dict[str, Any] | None" = None,
) -> "dict[str, Any] | None":
    """Parse a free-text workflow description with the selected agent.

    Merges the result with base_workflow (agent inference) so prior findings
    are not lost — user's explicit text takes precedence over inferred values.
    Returns a full workflow dict or None on failure.
    """
    import sys as _sys
    from harness_core.workflow_steps import answers_to_workflow

    base_ctx = ""
    if base_workflow:
        base_ctx = (
            f"\nFor context, the agent previously inferred these values from git history "
            f"(use them as a starting point and override with what the user described):\n"
            f"  ticket_system:  {base_workflow.get('ticket_system', '')}\n"
            f"  ticket_url:     {base_workflow.get('ticket_url', '')}\n"
            f"  base_branch:    {base_workflow.get('base_branch', '')}\n"
            f"  branch_pattern: {base_workflow.get('branch_pattern', '')}\n"
            f"  build_cmd:      {base_workflow.get('build_cmd', '')}\n"
            f"  critical_rules: {base_workflow.get('critical_rules', [])}\n"
        )

    prompt = (
        f"The developer described their project workflow as follows:\n"
        f"\n"
        f"\"{user_text}\"\n"
        f"{base_ctx}\n"
        f"Extract workflow fields from the description above and fill in this JSON template.\n"
        f"If the description doesn't mention a field, use an empty string (or the inferred value).\n"
        f"Respond with only the completed JSON:\n"
        f"\n"
        f"{_WORKFLOW_SCHEMA}\n"
    )

    raw: str | None = None
    if agent_name == "claude":
        raw = _invoke_claude(root, prompt)
    elif agent_name == "codex":
        raw = _invoke_codex(root, prompt)
    elif agent_name == "antigravity":
        raw = _invoke_antigravity(root, prompt)
    elif agent_name.startswith("ollama:"):
        raw = _invoke_ollama(agent_name[len("ollama:"):], prompt)

    if not raw:
        return None

    parsed = _parse_workflow_json(raw)
    if parsed is None:
        preview = raw[:200].replace("\n", " ")
        _sys.stdout.write(f"  ! workflow JSON parse failed. Preview: {preview!r}\n")
        _sys.stdout.flush()
        return None

    # Merge: prefer explicit user values, fall back to inferred
    if base_workflow:
        for field in ("ticket_system", "ticket_url", "base_branch", "branch_pattern", "build_cmd"):
            if not parsed.get(field) and base_workflow.get(field):
                parsed[field] = base_workflow[field]
        if not parsed.get("critical_rules") and base_workflow.get("critical_rules"):
            parsed["critical_rules"] = base_workflow["critical_rules"]
        if not parsed.get("context_files") and base_workflow.get("context_files"):
            parsed["context_files"] = base_workflow["context_files"]

    grill_answers = {
        "wf_ticket_system":  parsed.get("ticket_system", ""),
        "wf_ticket_url":     parsed.get("ticket_url", ""),
        "wf_base_branch":    parsed.get("base_branch", ""),
        "wf_branch_pattern": parsed.get("branch_pattern", ""),
        "wf_context_files":  ", ".join(parsed.get("context_files", [])),
        "wf_build_cmd":      parsed.get("build_cmd", ""),
        "wf_critical_rules": "\\n".join(parsed.get("critical_rules", [])),
    }
    return answers_to_workflow(grill_answers)


# ── Persistence ───────────────────────────────────────────────────────────────

def save_research(root: Path, data: dict[str, Any]) -> Path:
    """Persist agent research to .harness/agent_research.json."""
    path = root / ".harness" / "agent_research.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_research(root: Path) -> dict[str, Any] | None:
    """Load agent research from .harness/agent_research.json. Returns None if absent."""
    path = root / ".harness" / "agent_research.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
