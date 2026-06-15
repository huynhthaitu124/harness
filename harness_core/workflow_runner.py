"""Workflow command — agent-driven task execution with optional grill/plan mode.

Modes
-----
grill  User typed "plan" / "grill me" / "spec" etc., or LLM decided it's complex.
       → interactive Q&A session → spec HTML → agent executes with full context.
quick  Trivial fix: typo, rename, color, route.
       → no planning → agent executes immediately.
auto   LLM (Ollama) decides.  Falls back to grill when Ollama is unavailable.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Mode detection ─────────────────────────────────────────────────────────────

_GRILL_TRIGGERS = frozenset({
    "plan", "planning", "grill", "grill me",
    "spec", "design", "architect", "architecture",
    "requirements", "scope", "brainstorm",
    "new feature", "feature", "implement", "build",
    "how should", "what should", "help me think", "think through",
})
_QUICK_TRIGGERS = frozenset({
    "typo", "wording", "rename", "color", "colour",
    "css", "style", "route", "url", "link",
    "comment", "remove", "tweak", "bump", "move",
})


def detect_mode(task: str) -> str:
    """'grill' | 'quick' | 'auto' — heuristic from task keywords."""
    low = task.lower()
    if any(kw in low for kw in _GRILL_TRIGGERS):
        return "grill"
    if any(kw in low for kw in _QUICK_TRIGGERS):
        return "quick"
    return "auto"


def _llm_classify(task: str) -> str:
    """Ask Ollama: complex task needing planning, or simple fix? Returns 'grill'|'quick'."""
    from harness_core.project_analyzer import _call_ollama
    prompt = (
        f"Task: {task}\n\n"
        "Does this task require architecture planning, requirements clarification, or design decisions?\n"
        "Answer ONLY 'yes' (needs planning) or 'no' (straightforward fix/change).\n"
        "Yes → new feature, API design, complex refactor, integration.\n"
        "No  → typo, rename, color/text change, simple bug fix, minor UI tweak."
    )
    resp = _call_ollama(prompt, timeout=20)
    if resp and resp.strip().lower().startswith("yes"):
        return "grill"
    return "quick"


def resolve_mode(task: str) -> str:
    """Resolve 'auto' via Ollama. Falls back to 'grill' (safe default) when unavailable."""
    mode = detect_mode(task)
    if mode != "auto":
        return mode
    try:
        return _llm_classify(task)
    except Exception:
        return "grill"


# ── Grill session — questions & answers ────────────────────────────────────────

_FALLBACK_QUESTIONS = [
    "What is the expected end result? Describe it as a user would see it.",
    "Are there any constraints or things that must NOT change?",
    "What does 'done' look like — how will you verify the task is complete?",
    "Which areas of the codebase are likely involved?",
]


def generate_grill_questions(
    task: str,
    project_name: str,
    language: str,
    context_snippet: str = "",
) -> list[str]:
    """Generate 4 targeted clarifying questions for this task via Ollama."""
    from harness_core.project_analyzer import _call_ollama
    ctx = f"Project context:\n{context_snippet[:600]}\n\n" if context_snippet else ""
    prompt = (
        f"Project: {project_name} ({language})\n"
        f"Task: {task}\n\n{ctx}"
        "Generate exactly 4 concise clarifying questions an engineer must answer before "
        "starting this task.  Focus on: scope boundaries, success criteria, constraints, "
        "and known risks.  One question per line, no numbering, no preamble, each ending with '?'."
    )
    resp = _call_ollama(prompt, timeout=40)
    if resp:
        lines = [l.strip().lstrip("-•*0123456789. )") for l in resp.strip().splitlines() if l.strip()]
        questions = [q for q in lines if len(q) > 10 and "?" in q][:5]
        if len(questions) >= 2:
            return questions
    return _FALLBACK_QUESTIONS


# ── Plan generation ────────────────────────────────────────────────────────────

def generate_plan(task: str, answers: dict[str, str], language: str) -> str:
    """Generate step-by-step implementation plan from Q&A via Ollama."""
    from harness_core.project_analyzer import _call_ollama
    qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())
    prompt = (
        f"Language/framework: {language}\nTask: {task}\n\nPlanning Q&A:\n{qa_text}\n\n"
        "Write a concise step-by-step implementation plan (5-8 steps, markdown bullet list). "
        "Each step must start with a verb and be specific enough to implement. No fluff."
    )
    resp = _call_ollama(prompt, timeout=50)
    return resp.strip() if resp else ""


# ── Spec HTML ──────────────────────────────────────────────────────────────────

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
    plan: str,
    project_name: str,
    agent_name: str,
) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mode_color = "#24745a" if mode == "grill" else "#9a6400"

    qa_html = ""
    if answers:
        rows = "".join(
            f"<div class='qa'>"
            f"<div class='q'>{_e(q)}</div>"
            f"<div class='a'>{_e(a)}</div>"
            f"</div>"
            for q, a in answers.items()
        )
        qa_html = f"<h2>Requirements &amp; Clarifications</h2>{rows}"

    plan_html = _md_list_to_html(plan) if plan else "<p><em>No plan generated — quick mode.</em></p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spec — {_e(task[:60])}</title>
<style>
:root{{--paper:#f5f2eb;--ink:#172033;--muted:#667085;--line:#d8d0c2;--blue:#15476f}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--paper);color:var(--ink);font:16px/1.6 Georgia,serif;
      max-width:780px;margin:0 auto;padding:48px 24px}}
h1{{font:700 1.7rem/1.2 ui-sans-serif,system-ui,sans-serif;margin-bottom:8px}}
h2{{font:600 1rem/1.3 ui-sans-serif,system-ui,sans-serif;
    margin:32px 0 10px;color:var(--blue);text-transform:uppercase;letter-spacing:.05em}}
.meta{{color:var(--muted);font-size:.82rem;margin-bottom:36px;
       font-family:ui-sans-serif,system-ui,sans-serif}}
.badge{{display:inline-block;padding:3px 10px;border-radius:4px;
        font:700 .75rem/1.4 ui-sans-serif,system-ui,sans-serif;
        background:{mode_color};color:#fff;margin-right:6px;vertical-align:middle}}
.qa{{border-left:3px solid var(--line);padding:10px 16px;margin-bottom:14px}}
.q{{font-style:italic;color:var(--muted);font-size:.88rem;margin-bottom:4px}}
.a{{font-size:.95rem}}
ul{{padding-left:1.4em;margin-top:4px}}
li{{margin-bottom:8px}}
hr{{border:none;border-top:1px solid var(--line);margin:40px 0}}
code{{font-family:ui-monospace,monospace;font-size:.85em;background:#e8e3d8;
      padding:1px 4px;border-radius:3px}}
footer{{color:var(--muted);font-size:.78rem;margin-top:24px}}
</style>
</head>
<body>

<span class="badge">{_e(mode.upper())}</span>
<span class="badge" style="background:var(--muted)">{_e(project_name)}</span>
<h1>{_e(task)}</h1>
<div class="meta">Generated {today} · Agent: {_e(agent_name)}</div>

{qa_html}

<h2>Implementation Plan</h2>
{plan_html}

<hr>
<footer>
  Spec file lives in <code>.harness/specs/</code>.
  Loaded automatically by <code>harness_ticket_context</code> when this task is referenced.
</footer>
</body>
</html>"""


# ── Evaluation — detect reusable patterns ─────────────────────────────────────

def check_should_evaluate(task: str, answers: dict[str, str]) -> tuple[bool, str]:
    """Return (should_save, reason). True when Q&A reveals a reusable workflow pattern."""
    from harness_core.project_analyzer import _call_ollama
    qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())
    prompt = (
        f"Task: {task}\n\nQ&A:\n{qa_text}\n\n"
        "Does this planning session reveal a REUSABLE WORKFLOW PATTERN for this project? "
        "(e.g. a standard checklist, recurring constraint, or process the team always follows)\n"
        "Answer 'yes: <one-line reason>' or 'no'."
    )
    resp = _call_ollama(prompt, timeout=20)
    if resp:
        low = resp.strip().lower()
        if low.startswith("yes"):
            reason = resp.strip()[3:].strip(" :\n") or "reusable workflow pattern detected"
            return True, reason
    return False, ""


# ── Persistence ────────────────────────────────────────────────────────────────

def _task_slug(task: str) -> str:
    return re.sub(r"[^\w]+", "-", task.lower())[:40].strip("-")


def save_spec(target_root: Path, task: str, html: str) -> Path:
    """Write spec HTML to .harness/specs/<date>-<slug>.html and return the path."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = target_root / ".harness" / "specs" / f"{date}-{_task_slug(task)}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def save_evaluation(target_root: Path, task: str, reason: str, answers: dict[str, str]) -> Path:
    """Write workflow evaluation JSON to .harness/evaluations/."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = target_root / ".harness" / "evaluations" / f"{date}-{_task_slug(task)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "task":        task,
        "pattern":     reason,
        "qa":          answers,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# ── Agent prompt ───────────────────────────────────────────────────────────────

def build_workflow_prompt(
    task: str,
    mode: str,
    answers: dict[str, str],
    plan: str,
    spec_path: Path | None,
    target_root: Path,
) -> str:
    """Build the full prompt to hand off to the executing agent."""
    qa_block = ""
    if answers:
        qa_block = "\n== REQUIREMENTS (grill session) ==\n"
        qa_block += "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())

    plan_block = f"\n== IMPLEMENTATION PLAN ==\n{plan}" if plan else ""
    spec_block = f"\n== SPEC FILE ==\n{spec_path}" if spec_path else ""

    mode_instruction = (
        "Follow the implementation plan above step by step. "
        "Check each step off before moving to the next."
        if mode == "grill" else
        "This is a lightweight task — implement directly, no ceremony needed."
    )

    return (
        f"== HARNESS WORKFLOW TASK ==\n"
        f"Mode : {mode}\n"
        f"Root : {target_root}\n"
        f"Task : {task}\n"
        f"{spec_block}"
        f"{qa_block}"
        f"{plan_block}"
        f"\n\n== EXECUTION RULES ==\n"
        f"1. Call harness_ticket_context(root=\"{target_root}\", task=\"{task}\") FIRST.\n"
        f"2. {mode_instruction}\n"
        f"3. After finishing, call harness_record_memory with key decisions made.\n"
        f"4. If you discover a pattern worth remembering, add it to memory with kind='workflow'.\n"
    )


# ── Agent invocation ───────────────────────────────────────────────────────────

def _invoke_agent(agent_name: str, prompt: str, root: Path) -> int:
    """Invoke the selected agent CLI with the workflow prompt. Returns exit code."""
    import subprocess, sys, threading

    if agent_name == "claude":
        cmd = ["claude", "--print", "-p", "--allowedTools", "ALL"]
    elif agent_name == "codex":
        cmd = ["codex", "--approval-mode", "full-auto"]
    elif agent_name.startswith("ollama:"):
        model = agent_name[len("ollama:"):]
        cmd = ["ollama", "run", model]
    else:
        # antigravity / gemini — best effort
        cmd = ["antigravity", "run"] if _which("antigravity") else ["gemini"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(root),
        )

        def _reader(pipe):
            try:
                for line in pipe:
                    sys.stdout.write(line)
                    sys.stdout.flush()
            except Exception:
                pass

        t = threading.Thread(target=_reader, args=(proc.stdout,), daemon=True)
        t.start()
        proc.stdin.write(prompt)
        proc.stdin.close()
        proc.wait()
        t.join(timeout=5)
        return proc.returncode or 0
    except FileNotFoundError:
        return 2
    except Exception as exc:
        sys.stdout.write(f"Agent invocation error: {exc}\n")
        return 1


def _which(name: str) -> bool:
    import shutil
    return bool(shutil.which(name))
