from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from harness_core.research_registry import (
    due_research_sources,
    init_research_registry,
    record_source_check,
    refresh_research_sources,
)


class ResearchRegistryTests(unittest.TestCase):
    def test_never_checked_source_is_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            init_research_registry(path, [{"title": "MCP", "url": "https://example.test/mcp", "refresh_days": 7}])

            due = due_research_sources(path)

        self.assertEqual("never_checked", due[0]["due_reason"])

    def test_recent_source_is_not_due_but_stale_source_is_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            init_research_registry(path, [{"title": "Codex", "url": "https://example.test/codex", "refresh_days": 7}])
            now = datetime(2026, 6, 15, tzinfo=timezone.utc)
            record_source_check(path, "https://example.test/codex", content_hash="a", checked_at=now)

            recent = due_research_sources(path, now=now + timedelta(days=3))
            stale = due_research_sources(path, now=now + timedelta(days=8))

        self.assertEqual([], recent)
        self.assertEqual("stale", stale[0]["due_reason"])

    def test_changed_content_hash_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            url = "https://example.test/ollama"
            init_research_registry(path, [{"title": "Ollama", "url": url}])
            record_source_check(path, url, content_hash="old")

            result = record_source_check(path, url, content_hash="new", findings=["structured output changed"])

        self.assertTrue(result["changed"])
        self.assertEqual(1, result["findings_count"])

    def test_refresh_fetches_due_source_and_records_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            url = "https://example.test/codex"
            init_research_registry(path, [{"title": "Codex", "url": url}])

            report = refresh_research_sources(path, fetcher=lambda requested: b"current docs")

        self.assertEqual(1, report["checked_count"])
        self.assertEqual([], report["errors"])
        self.assertFalse(report["checked"][0]["changed"])

    def test_refresh_error_keeps_source_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            url = "https://example.test/fail"
            init_research_registry(path, [{"title": "Fail", "url": url}])

            def fail_fetch(_: str) -> bytes:
                raise OSError("offline")

            report = refresh_research_sources(path, fetcher=fail_fetch)
            due = due_research_sources(path)

        self.assertEqual(1, len(report["errors"]))
        self.assertEqual("never_checked", due[0]["due_reason"])

    def test_refresh_ignores_dynamic_script_changes_in_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            url = "https://example.test/dynamic"
            init_research_registry(path, [{"title": "Dynamic", "url": url}])
            responses = iter(
                [
                    b"<html><body><h1>Stable docs</h1><script>nonce=one</script></body></html>",
                    b"<html><body><h1>Stable docs</h1><script>nonce=two</script></body></html>",
                ]
            )

            refresh_research_sources(path, fetcher=lambda _: next(responses), force=True)
            second = refresh_research_sources(path, fetcher=lambda _: next(responses), force=True)

        self.assertEqual(0, second["changed_count"])


if __name__ == "__main__":
    unittest.main()
