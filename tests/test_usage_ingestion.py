import tempfile
import unittest
from pathlib import Path

from harness_core.token_ledger import summarize_usage
from harness_core.usage_ingestion import ingest_usage, parse_claude_usage, parse_codex_usage


class UsageIngestionTests(unittest.TestCase):
    def test_parses_claude_cache_usage(self):
        parsed = parse_claude_usage(
            '{"usage":{"input_tokens":10,"cache_creation_input_tokens":20,"cache_read_input_tokens":30,"output_tokens":5},"total_cost_usd":0.1}'
        )

        self.assertEqual(60, parsed["input_tokens"])
        self.assertEqual(5, parsed["output_tokens"])
        self.assertEqual(30, parsed["attribution"]["cache_read_input_tokens"])

    def test_parses_codex_jsonl_usage(self):
        parsed = parse_codex_usage(
            '{"type":"turn.started"}\n{"type":"usage","usage":{"input_tokens":100,"output_tokens":15,"cached_input_tokens":40}}\n'
        )

        self.assertEqual(100, parsed["input_tokens"])
        self.assertEqual(40, parsed["attribution"]["cached_input_tokens"])

    def test_ingests_usage_into_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "usage.jsonl"
            ingest_usage(
                ledger,
                center="claude",
                raw_output='{"usage":{"input_tokens":10,"output_tokens":2}}',
                label="harness-test",
            )
            report = summarize_usage(ledger)

        self.assertEqual(10, report["by_center"]["claude"]["input_tokens"])
        self.assertEqual(2, report["by_center"]["claude"]["output_tokens"])


if __name__ == "__main__":
    unittest.main()
