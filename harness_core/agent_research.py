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
        "auth_cmd":    ["claude", "auth", "login"],
        "auth_url":    "https://claude.ai/settings/cli",
        "auth_note":   "Opens your browser to log in with your Anthropic account.",
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
        "auth_cmd":    None,
        "auth_url":    "https://platform.openai.com/api-keys",
        "auth_note":   "Create an API key at platform.openai.com then:\nexport OPENAI_API_KEY=sk-...",
    })

    # ── Antigravity CLI ───────────────────────────────────────────────────────
    ag_path = shutil.which("antigravity")
    ag_inst  = bool(ag_path)
    agents.append({
        "name":        "antigravity",
        "label":       "Antigravity",
        "available":   ag_inst,
        "installed":   ag_inst,
        "authed":      ag_inst,
        "detail":      ag_path or "not found",
        "model":       None,
        "install_how": None,
        "install_pkg": None,
        "auth_cmd":    None,
        "auth_url":    None,
        "auth_note":   "",
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


def _build_research_prompt(root: Path, analysis: dict[str, Any], context: str) -> str:
    project_name = analysis.get("project_name", root.name)
    language     = analysis.get("language", "unknown")
    framework    = analysis.get("framework", "") or "—"
    entry_points = analysis.get("entry_points") or []
    agents       = analysis.get("agents") or []

    ep_str    = ", ".join(str(e) for e in entry_points[:3]) or "—"
    agent_str = ", ".join(a.get("agent", str(a)) if isinstance(a, dict) else str(a) for a in agents[:4]) or "none"

    return (
        f"Please help document the {project_name} project for its development team.\n"
        f"\n"
        f"Project details:\n"
        f"- Location: {root}\n"
        f"- Language: {language}, Framework: {framework}\n"
        f"- Entry points: {ep_str}\n"
        f"- Agent configs: {agent_str}\n"
        f"\n"
        f"Here is the content of the key files to base your analysis on:\n"
        f"\n"
        f"{context}\n"
        f"\n"
        f"Based on the files above, please fill in this JSON documentation template with accurate,\n"
        f"specific information about this project. Replace the placeholder text with real findings.\n"
        f"Keep each 'id' field unchanged. Respond with the completed JSON:\n"
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
    from harness_core.project_analyzer import build_analysis_context, extract_key_files

    key_files = extract_key_files(root)
    context   = build_analysis_context(root, key_files)
    prompt    = _build_research_prompt(root, analysis, context)

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
