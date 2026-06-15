"""Terminal UI primitives — ANSI + raw input, no curses, no external deps.

Public API
----------
menu(title, items)           -> str | None   (↑↓ navigate, Enter launch, Esc/q quit)
confirm(prompt, default)     -> bool         (← → toggle, Enter confirm)
select(prompt, options)      -> str | None   (↑↓ move, Enter confirm)
"""
from __future__ import annotations

import os
import sys
from typing import NamedTuple


# ── ANSI ─────────────────────────────────────────────────────────────────────

_NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()

def _c(*codes: int) -> str:
    return "" if _NO_COLOR else f"\x1b[{';'.join(map(str, codes))}m"

RESET  = _c(0)
BOLD   = _c(1)
DIM    = _c(2)
CYAN   = _c(36)
GREEN  = _c(32)
YELLOW = _c(33)
WHITE  = _c(37)

def _up(n: int)    -> str: return f"\x1b[{n}A"
def _clr()         -> str: return "\x1b[2K\r"
def _hide_cursor() -> str: return "\x1b[?25l"
def _show_cursor() -> str: return "\x1b[?25h"


# ── raw keypress ──────────────────────────────────────────────────────────────

def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _read_key() -> str:
    import tty, termios
    fd  = sys.stdin.fileno()
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


# ── menu (Ollama style) ───────────────────────────────────────────────────────

class MenuItem(NamedTuple):
    key:   str          # returned when selected
    label: str          # bold first line
    desc:  str = ""     # dim second line (optional)


def menu(title: str, items: list[MenuItem], version: str = "") -> str | None:
    """Display an Ollama-style interactive menu.

    Returns the `key` of the selected item, or None if user pressed Esc/q.
    Falls back to numbered prompt when stdin is not a tty.
    """
    if not _is_tty():
        print(f"\n{title}")
        for i, item in enumerate(items):
            print(f"  {i + 1}. {item.label}")
        raw = input(f"Enter number [1-{len(items)}]: ").strip()
        try:
            return items[int(raw) - 1].key
        except (ValueError, IndexError):
            return None

    idx        = 0
    line_count = 0

    def _render(first: bool = False) -> int:
        out = []
        if first:
            # title + version header
            header = f"{BOLD}{title}{RESET}"
            if version:
                header += f"  {DIM}{version}{RESET}"
            out.append(header)
            out.append("")
        for i, item in enumerate(items):
            if i == idx:
                bullet = f"{CYAN}{BOLD}▸ {item.label}{RESET}"
                out.append(f"  {bullet}")
            else:
                out.append(f"    {DIM}{item.label}{RESET}")
            if item.desc:
                out.append(f"    {DIM}{item.desc}{RESET}")
            out.append("")
        out.append(f"{DIM}↑/↓ navigate  •  enter select  •  esc quit{RESET}")
        return out

    # first draw
    sys.stdout.write(_hide_cursor())
    lines = _render(first=True)
    line_count = len(lines)
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()

    def _redraw() -> None:
        nonlocal line_count
        sys.stdout.write(_up(line_count))
        new_lines = _render(first=True)
        for line in new_lines:
            sys.stdout.write(_clr() + line + "\n")
        line_count = len(new_lines)
        sys.stdout.flush()

    try:
        while True:
            key = _read_key()
            if key == "\x1b[A":   # up
                idx = (idx - 1) % len(items)
                _redraw()
            elif key == "\x1b[B": # down
                idx = (idx + 1) % len(items)
                _redraw()
            elif key in ("\r", "\n"):
                sys.stdout.write(_show_cursor() + "\n")
                return items[idx].key
            elif key in ("q", "Q", "\x1b"):
                sys.stdout.write(_show_cursor() + "\n")
                return None
    except KeyboardInterrupt:
        sys.stdout.write(_show_cursor() + "\n")
        return None


# ── confirm (← →) ────────────────────────────────────────────────────────────

def confirm(prompt: str, default: bool = True) -> bool:
    if not _is_tty():
        raw = input(f"{prompt} [y/n] ").strip().lower()
        return raw in ("y", "yes") or (raw == "" and default)

    choice = default

    def _render():
        yes = f"{BOLD}{GREEN} YES {RESET}" if choice     else f"{DIM} yes {RESET}"
        no  = f"{BOLD}{YELLOW} NO {RESET}"  if not choice else f"{DIM} no {RESET}"
        hint = f"  {DIM}◀ ▶ toggle  •  enter confirm  •  q skip{RESET}"
        sys.stdout.write(f"\r{_clr()}{BOLD}{prompt}{RESET}   {yes}  {no}{hint}  ")
        sys.stdout.flush()

    sys.stdout.write("\n")
    sys.stdout.write(_hide_cursor())
    _render()

    try:
        while True:
            key = _read_key()
            if key in ("\r", "\n"):
                sys.stdout.write(_show_cursor() + "\n")
                return choice
            if key == "\x1b[D":   # left  → YES
                choice = True;  _render()
            elif key == "\x1b[C": # right → NO
                choice = False; _render()
            elif key in ("q", "\x1b"):
                sys.stdout.write(_show_cursor() + "\n")
                return False
    except KeyboardInterrupt:
        sys.stdout.write(_show_cursor() + "\n")
        return False


# ── select (↑↓) ──────────────────────────────────────────────────────────────

def select(prompt: str, options: list[str], default: int = 0) -> str | None:
    if not options:
        return None

    if not _is_tty():
        print(f"\n{prompt}")
        for i, o in enumerate(options):
            print(f"  {i + 1}. {o}")
        raw = input(f"Enter number [1-{len(options)}]: ").strip()
        try:
            return options[max(0, min(int(raw) - 1, len(options) - 1))]
        except ValueError:
            return options[0]

    idx    = max(0, min(default, len(options) - 1))
    height = len(options) + 2  # rows printed below prompt

    def _render(first: bool = False):
        if first:
            sys.stdout.write(f"\n{BOLD}{prompt}{RESET}\n")
        for i, opt in enumerate(options):
            if i == idx:
                sys.stdout.write(_clr() + f"  {CYAN}{BOLD}❯ {opt}{RESET}\n")
            else:
                sys.stdout.write(_clr() + f"    {DIM}{opt}{RESET}\n")
        sys.stdout.write(_clr() + f"{DIM}↑/↓ move  •  enter select  •  q skip{RESET}\n")
        sys.stdout.flush()

    sys.stdout.write(_hide_cursor())
    _render(first=True)

    try:
        while True:
            key = _read_key()
            if key == "\x1b[A":
                idx = (idx - 1) % len(options)
            elif key == "\x1b[B":
                idx = (idx + 1) % len(options)
            elif key in ("\r", "\n"):
                sys.stdout.write(_show_cursor())
                # clear the list, print chosen inline
                sys.stdout.write(_up(height))
                for _ in range(height):
                    sys.stdout.write(_clr() + "\n")
                sys.stdout.write(_up(height))
                sys.stdout.write(f"  {GREEN}✓{RESET} {BOLD}{options[idx]}{RESET}\n")
                sys.stdout.flush()
                return options[idx]
            elif key in ("q", "Q", "\x1b"):
                sys.stdout.write(_show_cursor() + "\n")
                return None
            # redraw list only
            sys.stdout.write(_up(height - 1))  # back to first option row
            for i, opt in enumerate(options):
                if i == idx:
                    sys.stdout.write(_clr() + f"  {CYAN}{BOLD}❯ {opt}{RESET}\n")
                else:
                    sys.stdout.write(_clr() + f"    {DIM}{opt}{RESET}\n")
            sys.stdout.write(_clr() + f"{DIM}↑/↓ move  •  enter select  •  q skip{RESET}\n")
            sys.stdout.flush()
    except KeyboardInterrupt:
        sys.stdout.write(_show_cursor() + "\n")
        return None
