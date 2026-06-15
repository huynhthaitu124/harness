"""Workflow runner — multi-agent orchestration for task execution.

Architecture
────────────
1. Build RAG context pack for the task  (harness_agent_rag_pack)
2. Center agent (preferred_center) runs grill session / detects mode
3. Center agent plans phases + assigns each to best available agent:
       design     → research-oriented agent (Antigravity / Claude)
       implement  → code-gen agent (Codex / Claude)
       test       → Codex / Claude
       verify     → center agent (always)
4. If no subordinates are available → center does every phase itself.

The center agent is the project manager; subordinates are specialists.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Mode detection ─────────────────────────────────────────────────────────────

_GRILL_TRIGGERS = frozenset({
    "plan", "planning", "grill", "grill me", "spec", "design", "architect",
    "architecture", "requirements", "scope", "brainstorm", "think",
    "new feature", "feature", "implement", "build", "how should", "what should",
})
_QUICK_TRIGGERS = frozenset({
    "typo", "wording", "rename", "color", "colour", "css", "style",
    "route", "url", "link", "comment", "remove", "tweak", "bump", "move",
})


def detect_mode(task: str) -> str:
    """'grill' | 'quick' | 'auto' — heuristic from task keywords."""
    low = task.lower()
    if any(kw in low for kw in _GRILL_TRIGGERS):
        return "grill"
    if any(kw in low for kw in _QUICK_TRIGGERS):
        return "quick"
    return "auto"


def resolve_mode(task: str) -> str:
    """Resolve 'auto' via Ollama; fall back to 'grill' for longer tasks."""
    mode = detect_mode(task)
    if mode != "auto":
        return mode
    # Try Ollama to decide
    try:
        from harness_core.project_analyzer import _call_ollama
        prompt = (
            f"Task: {task}\n\n"
            "Is this task complex enough to require planning (architecture decisions, "
            "multi-file changes, new features) or is it a small quick fix?\n"
            "Answer with ONE word: 'grill' for complex, 'quick' for simple."
        )
        resp = (_call_ollama(prompt, timeout=15) or "").strip().lower()
        if "quick" in resp:
            return "quick"
        if "grill" in resp:
            return "grill"
    except Exception:
        pass
    # Default: longer tasks get planning session
    return "grill" if len(task.split()) >= 8 else "quick"


def check_should_evaluate(task: str, answers: dict[str, str]) -> tuple[bool, str]:
    """Decide if Q&A session reveals a reusable workflow pattern worth saving."""
    # Heuristics: task touches auth / payment / deploy / recurring workflows
    _PATTERN_KWORDS = {
        "auth", "authentication", "login", "payment", "billing", "deploy",
        "migration", "onboard", "notification", "report", "export", "import",
    }
    low = task.lower()
    for kw in _PATTERN_KWORDS:
        if kw in low:
            return True, f"Recurring pattern: {kw}"
    # If many detailed answers — likely a reusable workflow
    if sum(len(v) for v in answers.values()) > 300:
        return True, "Detailed workflow captured"
    return False, ""


# ── Agent roster ───────────────────────────────────────────────────────────────

_PHASE_AFFINITY: dict[str, list[str]] = {
    # phase → preferred agents in order
    "design":    ["antigravity", "claude"],
    "implement": ["codex", "claude", "antigravity"],
    "test":      ["codex", "claude"],
    "verify":    [],   # always center
}


def get_preferred_center(target_root: Path) -> str:
    """Return preferred_center from .harness/state.json, or 'claude' as default."""
    state_path = target_root / ".harness" / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            center = state.get("preferred_center", "auto")
            if center and center != "auto":
                return center
        except Exception:
            pass
    return "claude"


def get_agent_roster(target_root: Path) -> dict[str, Any]:
    """Detect available agents and return {center, subordinates}.

    Center = preferred_center from state.json.
    Subordinates = other available agents (CLI detected + Ollama).
    """
    from harness_core.agent_research import detect_agent_clis
    center = get_preferred_center(target_root)

    available = {
        a["name"]: a
        for a in detect_agent_clis()
        if a.get("available")
    }

    subordinates: list[dict[str, Any]] = []
    for name, info in available.items():
        # Subordinates = agents that are NOT the center
        if name != center and not name.startswith("ollama:"):
            subordinates.append(info)

    # Add Ollama models as lightweight subordinates
    for name, info in available.items():
        if name.startswith("ollama:"):
            subordinates.append(info)

    return {
        "center":       center,
        "center_avail": center in available,
        "subordinates": subordinates,
        "all_available": list(available.keys()),
    }


def _best_agent_for_phase(phase: str, subordinates: list[dict], center: str) -> str:
    """Pick the best available agent for a given phase."""
    if phase == "verify":
        return center
    names = {a["name"] for a in subordinates}
    for preferred in _PHASE_AFFINITY.get(phase, []):
        if preferred in names and preferred != center:
            return preferred
        # also check ollama prefix
        for n in names:
            if n.startswith("ollama:") and preferred == "ollama":
                return n
    return center  # fall back to center if no subordinate matches


# ── RAG context ────────────────────────────────────────────────────────────────

def build_rag_context(target_root: Path, task: str) -> tuple[str, Path | None]:
    """Build a RAG context pack for the task.

    Returns (content_str, pack_path | None).
    Uses build_agent_rag_pack() — same as `harness rag-pack`.
    Falls back to analysis context if RAG fails.
    """
    try:
        from harness_core.agent_rag import build_agent_rag_pack
        report = build_agent_rag_pack(target_root, task)
        pack_path_str = report.get("context_pack_path")
        if pack_path_str:
            pack_path = Path(pack_path_str)
            if pack_path.exists():
                return pack_path.read_text(encoding="utf-8", errors="ignore"), pack_path
    except Exception:
        pass

    # Fallback: analysis context
    try:
        from harness_core.project_analyzer import build_analysis_context, extract_key_files
        kf = extract_key_files(target_root)
        return build_analysis_context(target_root, kf, max_chars=4000), None
    except Exception:
        return "", None


# ── Center agent text generation ───────────────────────────────────────────────

def _invoke_for_text(agent_name: str, prompt: str, root: Path, timeout: int = 120) -> str | None:
    """Invoke agent CLI, capture and return stdout as text (also streams to terminal)."""
    if agent_name == "claude":
        cmds = [["claude", "--print"], ["claude", "-p"]]
    elif agent_name == "codex":
        cmds = [["codex", "--quiet"]]
    elif agent_name.startswith("ollama:"):
        model = agent_name[len("ollama:"):]
        # Ollama via HTTP is already handled by _call_ollama
        from harness_core.project_analyzer import _call_ollama
        return _call_ollama(prompt, timeout=timeout)
    elif agent_name in ("antigravity", "gemini"):
        cmds = [["antigravity", "ask"], ["gemini"]]
    else:
        return None

    for cmd_base in cmds:
        chunks: list[str] = []

        def _reader(pipe, store: list[str]) -> None:
            try:
                for line in pipe:
                    sys.stdout.write(f"    {line}")
                    sys.stdout.flush()
                    store.append(line)
            except Exception:
                pass

        try:
            proc = subprocess.Popen(
                cmd_base,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                cwd=str(root),
            )
            t = threading.Thread(target=_reader, args=(proc.stdout, chunks), daemon=True)
            t.start()
            proc.stdin.write(prompt)
            proc.stdin.close()
            proc.wait(timeout=timeout)
            t.join(timeout=5)
            text = "".join(chunks).strip()
            if text:
                return text
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        except Exception:
            continue

    return None


# ── Grill questions via center or Ollama ───────────────────────────────────────

_FALLBACK_QUESTIONS = [
    "What is the expected end result — describe it as a user would see it?",
    "Are there constraints or things that must NOT change?",
    "What does 'done' look like — how will you verify the task is complete?",
    "Which areas of the codebase are likely involved?",
]


def generate_grill_questions(
    center: str,
    task: str,
    rag_content: str,
    root: Path,
) -> list[str]:
    """Ask center agent (or Ollama fallback) to generate clarifying questions."""
    ctx = rag_content[:1200] if rag_content else ""
    prompt = (
        f"Task: {task}\n\n"
        + (f"Project context (RAG):\n{ctx}\n\n" if ctx else "")
        + "Generate exactly 4 concise clarifying questions an engineer must answer before "
        "starting this task. Focus on: scope, success criteria, constraints, affected areas. "
        "One question per line, no numbering, each ending with '?'. No preamble."
    )
    sys.stdout.write(f"  ┌─ {center} — generating questions ──────────────────────\n")
    sys.stdout.flush()
    raw = _invoke_for_text(center, prompt, root, timeout=60)
    sys.stdout.write("  └────────────────────────────────────────────────────────\n")
    sys.stdout.flush()

    if raw:
        lines = [l.strip().lstrip("-•*0123456789. )") for l in raw.splitlines() if l.strip()]
        questions = [q for q in lines if len(q) > 10 and "?" in q][:5]
        if len(questions) >= 2:
            return questions

    # Fallback to Ollama
    try:
        from harness_core.project_analyzer import _call_ollama
        resp = _call_ollama(prompt, timeout=40)
        if resp:
            lines = [l.strip().lstrip("-•*0123456789. )") for l in resp.splitlines() if l.strip()]
            questions = [q for q in lines if len(q) > 10 and "?" in q][:5]
            if len(questions) >= 2:
                return questions
    except Exception:
        pass

    return _FALLBACK_QUESTIONS


# ── Phase planning via center ──────────────────────────────────────────────────

_DEFAULT_PHASES_GRILL = ["design", "implement", "test", "verify"]
_DEFAULT_PHASES_QUICK = ["implement", "verify"]


def plan_phases(
    center: str,
    task: str,
    mode: str,
    answers: dict[str, str],
    rag_content: str,
    subordinates: list[dict],
    root: Path,
) -> list[dict[str, str]]:
    """Center agent produces phase plan with agent assignments.

    Each phase: {name, agent, description, prompt}
    Falls back to default assignment when center returns unparseable output.
    """
    sub_names = [a["name"] for a in subordinates]
    sub_desc  = ", ".join(sub_names) if sub_names else "none"
    qa_text   = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())
    ctx       = rag_content[:1500] if rag_content else ""
    phases    = _DEFAULT_PHASES_GRILL if mode == "grill" else _DEFAULT_PHASES_QUICK

    prompt = (
        f"You are the orchestrator for a software task.\n\n"
        f"Task: {task}\n"
        f"Mode: {mode}\n"
        + (f"\nQ&A:\n{qa_text}\n" if qa_text else "")
        + (f"\nProject context (RAG excerpt):\n{ctx}\n" if ctx else "")
        + f"\nAvailable subordinate agents: {sub_desc}\n"
        f"Phases needed: {', '.join(phases)}\n\n"
        f"For each phase, assign the most suitable agent and write a focused prompt.\n"
        f"'verify' must always be assigned to yourself (the center agent: {center}).\n"
        f"If a phase should use a subordinate, pick from: {sub_desc or center}.\n"
        f"If no subordinates available, assign everything to {center}.\n\n"
        f"Respond ONLY with valid JSON:\n"
        f'{{\n  "phases": [\n'
        f'    {{"name": "implement", "agent": "codex", '
        f'"description": "one sentence", "prompt": "full phase prompt here"}}\n'
        f'  ]\n}}'
    )

    sys.stdout.write(f"  ┌─ {center} — planning phases ─────────────────────────\n")
    sys.stdout.flush()
    raw = _invoke_for_text(center, prompt, root, timeout=120)
    sys.stdout.write("  └────────────────────────────────────────────────────────\n")
    sys.stdout.flush()

    if raw:
        parsed = _extract_json(raw)
        if parsed and "phases" in parsed:
            result = []
            for p in parsed["phases"]:
                if isinstance(p, dict) and "name" in p:
                    result.append({
                        "name":        p.get("name", ""),
                        "agent":       p.get("agent", center),
                        "description": p.get("description", ""),
                        "prompt":      p.get("prompt", ""),
                    })
            if result:
                return result

    # Fallback: default assignment with generic prompts
    return _default_phase_plan(task, mode, answers, center, subordinates)


def _default_phase_plan(
    task: str, mode: str, answers: dict, center: str, subordinates: list[dict]
) -> list[dict[str, str]]:
    qa = "\n".join(f"- {q}: {a}" for q, a in answers.items())
    base_ctx = f"Task: {task}\n" + (f"Requirements:\n{qa}" if qa else "")
    phases = _DEFAULT_PHASES_GRILL if mode == "grill" else _DEFAULT_PHASES_QUICK
    result = []
    for phase in phases:
        agent = _best_agent_for_phase(phase, subordinates, center)
        prompts = {
            "design":    f"{base_ctx}\n\nPhase: DESIGN\nProduce the architecture and API design for this task. "
                         "List key components, data flow, and interface contracts. Be concise.",
            "implement": f"{base_ctx}\n\nPhase: IMPLEMENT\nImplement the task. "
                         "Write clean, production-ready code. Follow existing patterns in the codebase.",
            "test":      f"{base_ctx}\n\nPhase: TEST\nWrite and run tests for the implementation. "
                         "Cover happy path, edge cases, and error conditions.",
            "verify":    f"{base_ctx}\n\nPhase: VERIFY\nReview all changes. "
                         "Check correctness, conventions, test coverage. Summarise what was done.",
        }
        result.append({
            "name":        phase,
            "agent":       agent,
            "description": phase.capitalize(),
            "prompt":      prompts.get(phase, base_ctx),
        })
    return result


def _extract_json(text: str) -> dict | None:
    """Extract first valid JSON object from a text string."""
    # Strip markdown fences
    text = re.sub(r"```[a-z]*\n?", "", text).strip()
    # Find first { ... }
    start = text.find("{")
    if start == -1:
        return None
    # Try increasingly larger substrings
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    return None


# ── Phase execution ────────────────────────────────────────────────────────────

def execute_phase(
    phase: dict[str, str],
    rag_content: str,
    rag_path: Path | None,
    spec_path: Path | None,
    target_root: Path,
    previous_output: str = "",
) -> str:
    """Execute one workflow phase. Returns agent output text."""
    from harness_core.agent_research import (
        _invoke_claude,
        _invoke_codex,
        _invoke_antigravity,
        _invoke_ollama,
    )

    agent   = phase["agent"]
    name    = phase["name"]
    prompt  = phase["prompt"]

    # Enrich prompt with RAG + harness context
    harness_ctx = (
        f"\n\n== HARNESS CONTEXT ==\n"
        f"Root: {target_root}\n"
        + (f"Spec: {spec_path}\n" if spec_path else "")
        + (f"RAG pack: {rag_path}\n" if rag_path else "")
        + "FIRST call: harness_ticket_context(root=\"" + str(target_root) + "\", "
        + f'task="[workflow:{name}] " + task) before reading any source file.\n'
    )

    rag_excerpt = f"\n\n== RAG CONTEXT ==\n{rag_content[:2000]}\n" if rag_content else ""
    prev_block  = f"\n\n== PREVIOUS PHASE OUTPUT ==\n{previous_output[:1500]}\n" if previous_output else ""

    full_prompt = prompt + harness_ctx + rag_excerpt + prev_block

    sys.stdout.write(f"\n  ┌─ [{name}] → {agent} ────────────────────────────────\n")
    sys.stdout.flush()

    output: str | None = None
    if agent == "claude":
        output = _invoke_claude(target_root, full_prompt)
    elif agent == "codex":
        output = _invoke_codex(target_root, full_prompt)
    elif agent in ("antigravity", "gemini"):
        output = _invoke_antigravity(target_root, full_prompt)
    elif agent.startswith("ollama:"):
        model  = agent[len("ollama:"):]
        output = _invoke_ollama(model, full_prompt)
    else:
        # Generic subprocess fallback
        output = _invoke_for_text(agent, full_prompt, target_root)

    sys.stdout.write(f"  └─ [{name}] done ─────────────────────────────────────\n")
    sys.stdout.flush()

    return output or ""


# ── Spec + evaluation ──────────────────────────────────────────────────────────

def _e(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _md_list_to_html(text: str) -> str:
    items = [
        l.strip().lstrip("-*•· 0123456789.")
        for l in text.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if not items:
        return "<p><em>(not generated)</em></p>"
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items if i) + "</ul>"


def generate_spec_html(
    task: str,
    mode: str,
    answers: dict[str, str],
    phases: list[dict[str, str]],
    project_name: str,
    center: str,
    subordinates: list[dict],
) -> str:
    today      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode_color = "#24745a" if mode == "grill" else "#9a6400"

    qa_html = ""
    if answers:
        rows = "".join(
            f"<div class='qa'><div class='q'>{_e(q)}</div>"
            f"<div class='a'>{_e(a)}</div></div>"
            for q, a in answers.items()
        )
        qa_html = f"<h2>Requirements &amp; Clarifications</h2>{rows}"

    phase_rows = "".join(
        f"<tr><td class='phase'>{_e(p['name'])}</td>"
        f"<td class='agent'>{_e(p['agent'])}</td>"
        f"<td>{_e(p.get('description',''))}</td></tr>"
        for p in phases
    )
    sub_list = ", ".join(a["name"] for a in subordinates) if subordinates else "none — center handles all"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spec — {_e(task[:60])}</title>
<style>
:root{{--paper:#f5f2eb;--ink:#172033;--muted:#667085;--line:#d8d0c2;--blue:#15476f;--green:#24745a}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--paper);color:var(--ink);font:16px/1.6 Georgia,serif;
      max-width:800px;margin:0 auto;padding:48px 24px}}
h1{{font:700 1.7rem/1.2 ui-sans-serif,system-ui,sans-serif;margin-bottom:8px}}
h2{{font:600 1rem/1.3 ui-sans-serif,system-ui,sans-serif;
    margin:32px 0 10px;color:var(--blue);text-transform:uppercase;letter-spacing:.05em}}
.meta{{color:var(--muted);font-size:.82rem;margin-bottom:36px;font-family:ui-sans-serif,system-ui,sans-serif}}
.badge{{display:inline-block;padding:3px 10px;border-radius:4px;
        font:700 .75rem/1.4 ui-sans-serif,system-ui,sans-serif;background:{mode_color};
        color:#fff;margin-right:6px;vertical-align:middle}}
.qa{{border-left:3px solid var(--line);padding:10px 16px;margin-bottom:14px}}
.q{{font-style:italic;color:var(--muted);font-size:.88rem;margin-bottom:4px}}
.a{{font-size:.95rem}}
table{{width:100%;border-collapse:collapse;font-family:ui-sans-serif,system-ui,sans-serif;font-size:.9rem}}
th{{text-align:left;padding:8px 12px;border-bottom:2px solid var(--line);font-size:.78rem;
    text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
td{{padding:8px 12px;border-bottom:1px solid var(--line)}}
.phase{{font-weight:700;color:var(--blue)}}
.agent{{font-family:ui-monospace,monospace;font-size:.85em;color:var(--green)}}
code{{font-family:ui-monospace,monospace;font-size:.85em;background:#e8e3d8;
      padding:1px 4px;border-radius:3px}}
hr{{border:none;border-top:1px solid var(--line);margin:40px 0}}
footer{{color:var(--muted);font-size:.78rem;margin-top:24px}}
</style>
</head>
<body>
<span class="badge">{_e(mode.upper())}</span>
<span class="badge" style="background:var(--muted)">{_e(project_name)}</span>
<h1>{_e(task)}</h1>
<div class="meta">
  Generated {today} · Center: <strong>{_e(center)}</strong>
  · Subordinates: {_e(sub_list)}
</div>

{qa_html}

<h2>Phase Plan</h2>
<table>
<thead><tr><th>Phase</th><th>Agent</th><th>Goal</th></tr></thead>
<tbody>{phase_rows}</tbody>
</table>

<hr>
<footer>
  Spec: <code>.harness/specs/</code> ·
  Read by <code>harness_ticket_context</code> when task is referenced.
</footer>
</body>
</html>"""


def _task_slug(task: str) -> str:
    return re.sub(r"[^\w]+", "-", task.lower())[:40].strip("-")


def save_spec(target_root: Path, task: str, html: str) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = target_root / ".harness" / "specs" / f"{date}-{_task_slug(task)}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def save_evaluation(target_root: Path, task: str, pattern: str, answers: dict) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = target_root / ".harness" / "evaluations" / f"{date}-{_task_slug(task)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "task":        task,
        "pattern":     pattern,
        "qa":          answers,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# ── Main orchestrator ──────────────────────────────────────────────────────────

def run_workflow(
    target_root: Path,
    task: str,
    mode: str,
    answers: dict[str, str],
    phases: list[dict[str, str]],
    rag_content: str,
    rag_path: Path | None,
    spec_path: Path | None,
    center: str,
) -> int:
    """Execute all workflow phases in sequence, passing output forward."""
    previous_output = ""
    for i, phase in enumerate(phases, 1):
        sys.stdout.write(
            f"\n  Phase {i}/{len(phases)}: {phase['name'].upper()} "
            f"→ {phase['agent']}\n"
        )
        sys.stdout.flush()

        output = execute_phase(
            phase       = phase,
            rag_content = rag_content,
            rag_path    = rag_path,
            spec_path   = spec_path,
            target_root = target_root,
            previous_output = previous_output,
        )
        previous_output = output

        # Save phase output to .harness/workflow-phases/
        phase_dir = target_root / ".harness" / "workflow-phases"
        phase_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = _task_slug(task)
        (phase_dir / f"{date}-{slug}-{phase['name']}.md").write_text(
            f"# Phase: {phase['name']} — {task}\n\n"
            f"Agent: {phase['agent']}\n\n"
            f"{output}\n",
            encoding="utf-8",
        )

    return 0
