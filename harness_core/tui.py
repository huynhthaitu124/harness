"""Minimal arrow-key interactive prompts (no external deps).

Public API
----------
confirm(prompt)              -> bool   (left/right to toggle, Enter to confirm)
select(prompt, options)      -> str    (up/down to move, Enter to confirm)
"""
from __future__ import annotations

import sys
import os


# ── raw terminal helpers ──────────────────────────────────────────────────────

def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _read_key() -> str:
    """Return one keypress as a string token.

    Escape sequences:
      UP    → '\x1b[A'
      DOWN  → '\x1b[B'
      RIGHT → '\x1b[C'
      LEFT  → '\x1b[D'
      ENTER → '\r' or '\n'
      q/ESC → 'q'
    """
    import tty
    import termios

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return "\x1b[" + ch3
            return "\x1b"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _clear_line(n: int = 1) -> None:
    for _ in range(n):
        sys.stdout.write("\x1b[1A\x1b[2K")
    sys.stdout.flush()


# ── ANSI color helpers ────────────────────────────────────────────────────────

_BOLD   = "\x1b[1m"
_DIM    = "\x1b[2m"
_GREEN  = "\x1b[32m"
_CYAN   = "\x1b[36m"
_YELLOW = "\x1b[33m"
_RESET  = "\x1b[0m"


def _no_ansi() -> bool:
    return os.environ.get("NO_COLOR") or not _is_tty()


def _style(text: str, *codes: str) -> str:
    if _no_ansi():
        return text
    return "".join(codes) + text + _RESET


# ── confirm (left / right) ────────────────────────────────────────────────────

def confirm(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question. ← / → to toggle, Enter to confirm.

    Falls back to plain input() when stdin is not a tty (CI, piped).
    """
    if not _is_tty():
        raw = input(f"{prompt} [y/n] ").strip().lower()
        return raw in ("y", "yes", "")

    choice = default

    def _render() -> None:
        yes_label = _style(" YES ", _BOLD, _GREEN) if choice else _style(" yes ", _DIM)
        no_label  = _style(" NO  ", _BOLD, _YELLOW) if not choice else _style(" no  ", _DIM)
        arrow_hint = _style("  ◀ ▶ toggle  Enter confirm  q skip", _DIM)
        sys.stdout.write(f"\r{_style(prompt, _BOLD)}   {yes_label}  {no_label}{arrow_hint}   ")
        sys.stdout.flush()

    sys.stdout.write("\n")
    _render()

    while True:
        key = _read_key()
        if key in ("\r", "\n"):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return choice
        if key in ("\x1b[C", "\x1b[D"):  # right → NO, left → YES
            choice = key == "\x1b[D"
            _render()
        if key in ("q", "\x1b"):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return False


# ── select (up / down) ────────────────────────────────────────────────────────

def select(prompt: str, options: list[str], default: int = 0) -> str | None:
    """Pick one item from a list. ↑ / ↓ to move, Enter to confirm, q to skip.

    Returns the selected string, or None if the user pressed q/Esc.
    Falls back to numbered input() when stdin is not a tty.
    """
    if not options:
        return None

    if not _is_tty():
        print(f"\n{prompt}")
        for i, opt in enumerate(options):
            print(f"  {i + 1}. {opt}")
        raw = input(f"Enter number [1-{len(options)}]: ").strip()
        try:
            idx = int(raw) - 1
            return options[max(0, min(idx, len(options) - 1))]
        except ValueError:
            return options[0]

    idx = max(0, min(default, len(options) - 1))
    height = len(options)

    def _render() -> None:
        for i, opt in enumerate(options):
            if i == idx:
                prefix = _style("  ❯ ", _CYAN, _BOLD)
                label  = _style(opt, _BOLD, _CYAN)
            else:
                prefix = "    "
                label  = _style(opt, _DIM)
            sys.stdout.write(f"{prefix}{label}\n")
        sys.stdout.write(_style("  ↑ ↓ move   Enter confirm   q skip\n", _DIM))
        sys.stdout.flush()

    sys.stdout.write(f"\n{_style(prompt, _BOLD)}\n")
    _render()

    while True:
        key = _read_key()
        if key == "\x1b[A":  # up
            idx = (idx - 1) % len(options)
        elif key == "\x1b[B":  # down
            idx = (idx + 1) % len(options)
        elif key in ("\r", "\n"):
            _clear_line(height + 1)
            sys.stdout.write(f"  {_style('✓', _GREEN)} {_style(options[idx], _BOLD)}\n")
            sys.stdout.flush()
            return options[idx]
        elif key in ("q", "\x1b"):
            _clear_line(height + 1)
            sys.stdout.write(_style("  skipped\n", _DIM))
            sys.stdout.flush()
            return None

        _clear_line(height + 1)
        _render()
