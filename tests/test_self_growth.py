import tempfile
import unittest
from pathlib import Path

from harness_core.self_growth import run_growth_cycle


class SelfGrowthTests(unittest.TestCase):
    def test_records_growth_cycle_with_sources_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_growth_cycle(
                root,
                topic="harness memory",
                sources=[{"title": "Harness Memory", "url": "https://example.test"}],
                actions=["Add memory ledger"],
            )

            self.assertTrue(Path(result["cycle_path"]).exists())
            self.assertEqual(result["action_count"], 1)


if __name__ == "__main__":
    unittest.main()
