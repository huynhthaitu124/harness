import json
import tempfile
import unittest
from pathlib import Path

from harness_core.retrieval_eval import evaluate_hybrid_dataset, evaluate_retrieval


class RetrievalEvalTests(unittest.TestCase):
    def test_passes_when_recall_and_mrr_meet_thresholds(self):
        cases = [
            {"id": "auth", "query": "login token", "expected_paths": ["auth.py"]},
            {"id": "billing", "query": "invoice", "expected_paths": ["billing.py"]},
        ]

        report = evaluate_retrieval(
            cases,
            retriever=lambda query, top_k: [{"path": "auth.py" if "login" in query else "billing.py"}],
            top_k=2,
            min_recall=1.0,
            min_mrr=1.0,
        )

        self.assertEqual("PASS", report["verdict"])
        self.assertEqual(1.0, report["recall_at_k"])

    def test_default_fails_when_expected_path_is_missing(self):
        cases = [{"id": "auth", "query": "login token", "expected_paths": ["auth.py"]}]

        report = evaluate_retrieval(cases, retriever=lambda query, top_k: [{"path": "notes.txt"}], top_k=1)

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertEqual(0.0, report["mrr"])

    def test_evaluates_hybrid_dataset_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.py").write_text("def login(token):\n    return bool(token)\n", encoding="utf-8")
            dataset = Path(tmp) / "dataset.json"
            dataset.write_text(
                json.dumps({"cases": [{"id": "auth", "query": "login token", "expected_paths": ["auth.py"]}]}),
                encoding="utf-8",
            )

            report = evaluate_hybrid_dataset(root, dataset, top_k=1)

        self.assertEqual("PASS", report["verdict"])


if __name__ == "__main__":
    unittest.main()
