from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def init_research_registry(path: Path, sources: list[dict[str, Any]]) -> dict[str, Any]:
    registry = {
        "version": 1,
        "sources": [
            {
                "title": source["title"],
                "url": source["url"],
                "category": source.get("category", "general"),
                "channel": source.get("channel", "stable"),
                "refresh_days": int(source.get("refresh_days", 7)),
                "last_checked": None,
                "content_hash": None,
                "changed": False,
                "findings_count": 0,
                "findings": [],
            }
            for source in sources
        ],
    }
    _write_registry(path, registry)
    return registry


def due_research_sources(path: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    registry = _read_registry(path)
    now = now or datetime.now(timezone.utc)
    due: list[dict[str, Any]] = []
    for source in registry["sources"]:
        item = dict(source)
        if not source.get("last_checked"):
            item["due_reason"] = "never_checked"
            item["age_days"] = None
            due.append(item)
            continue
        checked = _parse_datetime(source["last_checked"])
        age_days = (now - checked).total_seconds() / 86400
        if age_days >= int(source.get("refresh_days", 7)):
            item["due_reason"] = "stale"
            item["age_days"] = round(age_days, 2)
            due.append(item)
    return due


def record_source_check(
    path: Path,
    url: str,
    *,
    content_hash: str,
    findings: list[str] | None = None,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    registry = _read_registry(path)
    source = next((item for item in registry["sources"] if item["url"] == url), None)
    if source is None:
        raise ValueError(f"source is not registered: {url}")
    old_hash = source.get("content_hash")
    changed = old_hash is not None and old_hash != content_hash
    source["last_checked"] = (checked_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    source["previous_hash"] = old_hash
    source["content_hash"] = content_hash
    source["changed"] = changed
    source["findings"] = findings or []
    source["findings_count"] = len(source["findings"])
    _write_registry(path, registry)
    return dict(source)


def research_registry_report(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    registry = _read_registry(path)
    due = due_research_sources(path, now=now)
    changed = [source for source in registry["sources"] if source.get("changed")]
    return {
        "path": str(path),
        "source_count": len(registry["sources"]),
        "due_count": len(due),
        "changed_count": len(changed),
        "due": due,
        "changed": changed,
    }


def refresh_research_sources(
    path: Path,
    *,
    fetcher: Any | None = None,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    registry = _read_registry(path)
    sources = registry["sources"] if force else due_research_sources(path, now=now)
    checked: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    fetch = fetcher or _fetch_url
    for source in sources:
        try:
            content = fetch(source["url"])
            if isinstance(content, str):
                content = content.encode("utf-8")
            content_hash = _stable_content_hash(content)
            checked.append(
                record_source_check(
                    path,
                    source["url"],
                    content_hash=content_hash,
                    checked_at=now,
                )
            )
        except Exception as exc:
            errors.append({"url": source["url"], "error": str(exc)})
    return {
        "path": str(path),
        "checked_count": len(checked),
        "changed_count": sum(1 for source in checked if source["changed"]),
        "checked": checked,
        "errors": errors,
    }


def _read_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _fetch_url(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "tri-center-harness/0.1"})
    with urlopen(request, timeout=25) as response:
        return response.read()


def _stable_content_hash(content: bytes) -> str:
    text = content.decode("utf-8", errors="ignore")
    if "<html" in text.lower() or "<body" in text.lower():
        parser = _VisibleTextParser()
        parser.feed(text)
        normalized = " ".join(" ".join(parser.parts).split())
        content = normalized.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class _VisibleTextParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            cleaned = re.sub(r"\s+", " ", data).strip()
            if cleaned:
                self.parts.append(cleaned)
