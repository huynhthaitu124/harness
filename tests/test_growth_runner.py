import tempfile
import unittest
from pathlib import Path

from harness_core.growth_runner import run_evaluated_growth_cycle


class GrowthRunnerTests(unittest.TestCase):
    def test_runs_growth_cycle_records_usage_and_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_evaluated_growth_cycle(
                root,
                topic="local model worker",
                sources=[{"title": "Ollama", "url": "https://example.test"}],
                actions=["Add worker gate"],
                usage={"center": "codex", "input_tokens": 10, "output_tokens": 1, "cost_usd": 0.0},
                required_evidence=["cycle recorded", "usage recorded"],
            )

            self.assertEqual(result["evaluation"]["verdict"], "PASS")
            self.assertTrue((root / "production_artifacts" / "usage.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
