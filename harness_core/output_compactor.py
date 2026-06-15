from __future__ import annotations

import re
from collections import Counter
from typing import Any

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+Z\s+")
CRITICAL_RE = re.compile(r"error|failed|failure|exception|traceback|limit", re.IGNORECASE)
SIGNAL_RE = re.compile(r"warn|needs_work|\bpass\b", re.IGNORECASE)


def compact_tool_output(text: str, *, max_chars: int = 4000) -> dict[str, Any]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    lines = text.splitlines()
    keys = [_line_key(line) for line in lines]
    counts = Counter(keys)
    representatives: dict[str, str] = {}
    ordered_keys: list[str] = []
    seen: set[str] = set()
    for line, key in zip(lines, keys):
        if key in seen:
            continue
        seen.add(key)
        representatives[key] = line
        ordered_keys.append(key)
    records = [
        {
            "key": key,
            "count": counts[key],
            "display": f"{representatives[key]} [repeated {counts[key]} times]" if counts[key] > 1 else representatives[key],
        }
        for key in ordered_keys
    ]

    full = "\n".join(record["display"] for record in records)
    if len(full) <= max_chars:
        output = full
        represented = len(lines)
    else:
        priority_indexes: list[int] = []
        priority_indexes.extend(index for index, record in enumerate(records) if CRITICAL_RE.search(record["display"]))
        priority_indexes.extend(range(min(5, len(records))))
        priority_indexes.extend(range(max(0, len(records) - 5), len(records)))
        priority_indexes.extend(index for index, record in enumerate(records) if SIGNAL_RE.search(record["display"]))
        selected: list[str] = []
        selected_indexes: set[int] = set()
        represented = 0
        for index in priority_indexes:
            if index in selected_indexes:
                continue
            line = records[index]["display"]
            candidate = "\n".join(selected + [line])
            if len(candidate) > max_chars:
                continue
            selected.append(line)
            selected_indexes.add(index)
            represented += records[index]["count"]
        omitted = max(0, len(lines) - represented)
        marker = f"\n[omitted {omitted} lines]" if omitted else ""
        output = "\n".join(selected)
        if len(output) + len(marker) <= max_chars:
            output += marker
        elif len(output) > max_chars:
            output = output[:max_chars]
    compact_chars = len(output)
    raw_chars = len(text)
    savings = 0.0 if raw_chars == 0 else ((raw_chars - compact_chars) / raw_chars) * 100
    return {
        "raw_chars": raw_chars,
        "compact_chars": compact_chars,
        "savings_percent": round(savings, 2),
        "raw_lines": len(lines),
        "unique_lines": len(records),
        "omitted_lines": max(0, len(lines) - represented),
        "output": output,
    }


def _line_key(line: str) -> str:
    return TIMESTAMP_RE.sub("", line).strip()
