import tempfile
import unittest
from pathlib import Path

from harness_core.token_ledger import record_usage, summarize_usage


class TokenLedgerTests(unittest.TestCase):
    def test_records_usage_jsonl_and_summarizes_by_center(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usage.jsonl"

            record_usage(path, center="claude", input_tokens=1000, output_tokens=100, cost_usd=0.12)
            record_usage(path, center="claude", input_tokens=500, output_tokens=50, cost_usd=0.04)
            record_usage(path, center="codex", input_tokens=200, output_tokens=20, cost_usd=0.02)

            summary = summarize_usage(path)

            self.assertEqual(summary["by_center"]["claude"]["input_tokens"], 1500)
            self.assertAlmostEqual(summary["by_center"]["claude"]["cost_usd"], 0.16)
            self.assertEqual(summary["total"]["output_tokens"], 170)


if __name__ == "__main__":
    unittest.main()
