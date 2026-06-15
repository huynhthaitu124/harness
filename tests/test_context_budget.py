import tempfile
import unittest
from pathlib import Path

from harness_core.context_budget import (
    build_context_pack,
    estimate_tokens,
    measure_context_savings,
)


class ContextBudgetTests(unittest.TestCase):
    def test_estimates_tokens_from_text(self):
        self.assertGreaterEqual(estimate_tokens("one two three four"), 1)
        self.assertEqual(estimate_tokens(""), 0)

    def test_context_pack_is_smaller_than_raw_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("def auth():\n    return 'auth ok'\n" * 50, encoding="utf-8")
            (root / "b.py").write_text("def billing():\n    return 'billing ok'\n" * 50, encoding="utf-8")

            pack = build_context_pack(root, "auth", max_files=5, max_chars_per_file=200)
            savings = measure_context_savings(root, pack)

            self.assertIn("a.py", pack)
            self.assertLess(savings["compact_tokens"], savings["raw_tokens"])
            self.assertGreater(savings["savings_percent"], 0)


if __name__ == "__main__":
    unittest.main()
