import tempfile
import unittest
from pathlib import Path

from harness_core.evaluator import evaluate_evidence


class EvaluatorTests(unittest.TestCase):
    def test_passes_when_expected_evidence_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "feature_list.json").write_text("{}", encoding="utf-8")

            result = evaluate_evidence(root, required=["tests passed", "handoff recorded"], evidence=["tests passed", "handoff recorded"])

            self.assertEqual(result["verdict"], "PASS")

    def test_needs_work_when_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_evidence(Path(tmp), required=["tests passed"], evidence=[])

            self.assertEqual(result["verdict"], "NEEDS_WORK")
            self.assertIn("tests passed", result["missing"])


if __name__ == "__main__":
    unittest.main()
