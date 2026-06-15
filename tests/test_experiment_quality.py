import tempfile
import unittest
from pathlib import Path

from harness_core.experiment_quality import evaluate_experiment_output


class ExperimentQualityTests(unittest.TestCase):
    def test_passes_complete_output_with_real_repo_citations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a.md", "b.md", "c.py", "d.py", "e.json"):
                (root / name).write_text("evidence", encoding="utf-8")
            output = {
                "summary": "A concise architecture summary.",
                "citations": ["a.md", "b.md", "c.py", "d.py", "e.json"],
                "risks": ["quota exhaustion", "stale context", "unsafe local memory pressure"],
            }

            report = evaluate_experiment_output(root, output)

        self.assertEqual("PASS", report["verdict"])
        self.assertEqual(1.0, report["quality_score"])

    def test_default_fails_missing_or_escaped_citations_and_wrong_risk_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("evidence", encoding="utf-8")
            output = {
                "summary": "summary",
                "citations": ["a.md", "missing.md", "../secret", "a.md", "a.md"],
                "risks": ["one"],
            }

            report = evaluate_experiment_output(root, output)

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("citation_missing:missing.md", report["failures"])
        self.assertIn("citation_outside_root:../secret", report["failures"])
        self.assertIn("risk_count:1", report["failures"])
        self.assertLess(report["quality_score"], 1.0)

    def test_rejects_summary_over_word_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate_experiment_output(
                Path(tmp),
                {"summary": "word " * 251, "citations": [], "risks": []},
            )

        self.assertIn("summary_word_count:251", report["failures"])


if __name__ == "__main__":
    unittest.main()
