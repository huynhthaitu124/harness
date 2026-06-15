import json
import tempfile
import unittest
from pathlib import Path

from harness_core.token_experiment import (
    evaluate_token_evidence,
    ingest_claude_result,
    ingest_codex_jsonl,
    record_experiment_run,
    summarize_experiments,
)


class TokenExperimentTests(unittest.TestCase):
    def test_token_evidence_requires_valid_pairs_for_token_measured_centers(self):
        report = evaluate_token_evidence(
            {
                "valid_pair_count": 1,
                "invalid_pair_count": 0,
                "by_center": {
                    "codex": {"pair_count": 1, "average_token_savings_percent": 42.0}
                },
            }
        )

        self.assertEqual("INCOMPLETE", report["verdict"])
        self.assertEqual(["claude"], report["missing_centers"])

    def test_token_evidence_ignores_antigravity_for_token_regression(self):
        report = evaluate_token_evidence(
            {
                "valid_pair_count": 3,
                "invalid_pair_count": 0,
                "by_center": {
                    "codex": {"pair_count": 1, "average_token_savings_percent": 42.0},
                    "claude": {"pair_count": 1, "average_token_savings_percent": 20.0},
                    "antigravity": {"pair_count": 1, "average_token_savings_percent": -5.0},
                },
            }
        )

        self.assertEqual("PASS", report["verdict"])
        self.assertEqual([], report["non_saving_centers"])

    def test_reports_savings_for_valid_baseline_harness_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.jsonl"
            record_experiment_run(
                path,
                experiment_id="auth-1",
                task_fingerprint="auth-flow-v1",
                center="claude",
                variant="baseline",
                input_tokens=1000,
                output_tokens=200,
                quality_score=0.9,
            )
            record_experiment_run(
                path,
                experiment_id="auth-1",
                task_fingerprint="auth-flow-v1",
                center="claude",
                variant="harness",
                input_tokens=400,
                output_tokens=150,
                quality_score=0.9,
            )

            report = summarize_experiments(path)

        self.assertEqual(1, report["valid_pair_count"])
        self.assertEqual(0, report["invalid_pair_count"])
        self.assertAlmostEqual(54.17, report["pairs"][0]["token_savings_percent"], places=2)

    def test_rejects_pair_with_mismatched_task_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.jsonl"
            record_experiment_run(path, experiment_id="x", task_fingerprint="v1", center="codex", variant="baseline", input_tokens=100, output_tokens=10)
            record_experiment_run(path, experiment_id="x", task_fingerprint="v2", center="codex", variant="harness", input_tokens=50, output_tokens=10)

            report = summarize_experiments(path)

        self.assertEqual(1, report["invalid_pair_count"])
        self.assertIn("task_fingerprint_mismatch", report["invalid_pairs"][0]["reasons"])

    def test_rejects_pair_when_harness_quality_regresses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.jsonl"
            record_experiment_run(path, experiment_id="x", task_fingerprint="v1", center="antigravity", variant="baseline", input_tokens=100, output_tokens=10, quality_score=0.9)
            record_experiment_run(path, experiment_id="x", task_fingerprint="v1", center="antigravity", variant="harness", input_tokens=50, output_tokens=10, quality_score=0.6)

            report = summarize_experiments(path, quality_tolerance=0.05)

        self.assertIn("quality_regression", report["invalid_pairs"][0]["reasons"])

    def test_ingests_claude_json_token_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.jsonl"
            raw = json.dumps(
                {
                    "total_cost_usd": 0.12,
                    "usage": {
                        "input_tokens": 4,
                        "cache_creation_input_tokens": 100,
                        "cache_read_input_tokens": 500,
                        "output_tokens": 40,
                    },
                }
            )

            entry = ingest_claude_result(
                path,
                raw,
                experiment_id="claude-1",
                task_fingerprint="task-v1",
                variant="harness",
            )

        self.assertEqual(604, entry["input_tokens"])
        self.assertEqual(40, entry["output_tokens"])
        self.assertEqual(0.12, entry["cost_usd"])

    def test_ingests_codex_jsonl_usage_event_and_ignores_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.jsonl"
            raw = (
                "2026-01-01 WARN noisy line\n"
                '{"type":"thread.started","thread_id":"abc"}\n'
                '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":40,"output_tokens":20}}\n'
            )

            entry = ingest_codex_jsonl(
                path,
                raw,
                experiment_id="codex-1",
                task_fingerprint="task-v1",
                variant="baseline",
            )

        self.assertEqual(100, entry["input_tokens"])
        self.assertEqual(20, entry["output_tokens"])
        self.assertEqual(40, entry["metadata"]["cached_input_tokens"])

    def test_codex_ingest_rejects_output_without_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiments.jsonl"

            with self.assertRaises(ValueError):
                ingest_codex_jsonl(
                    path,
                    '{"type":"turn.failed","error":{"message":"usage limit"}}\n',
                    experiment_id="codex-fail",
                    task_fingerprint="task-v1",
                    variant="baseline",
                )


if __name__ == "__main__":
    unittest.main()
