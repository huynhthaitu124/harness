import json
import tempfile
import unittest
from pathlib import Path

from harness_core.experiment_scheduler import (
    build_experiment_blueprint,
    init_experiment_queue,
    plan_next_experiment,
    prepare_experiment_run,
)
from harness_core.token_experiment import record_experiment_run


class ExperimentSchedulerTests(unittest.TestCase):
    def test_initializes_reproducible_tri_center_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"

            queue = init_experiment_queue(path)

            self.assertEqual(["claude", "codex", "antigravity"], queue["center_order"])
            self.assertEqual("harness-architecture-summary-v1", queue["tasks"][0]["id"])
            self.assertTrue(queue["tasks"][0]["task_fingerprint"])
            self.assertEqual(queue, json.loads(path.read_text(encoding="utf-8")))

    def test_blocks_without_a_ready_center_and_preserves_reset_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.json"
            init_experiment_queue(queue_path)

            plan = plan_next_experiment(
                queue_path,
                Path(tmp) / "experiments.jsonl",
                {"ready_centers": [], "centers": {"claude": {"quota": {"reset_hint": "01:50"}}}},
            )

        self.assertEqual("BLOCKED", plan["verdict"])
        self.assertEqual("01:50", plan["reset_hints"]["claude"])

    def test_plans_baseline_then_harness_for_cheapest_ready_center(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "queue.json"
            experiments_path = root / "experiments.jsonl"
            queue = init_experiment_queue(queue_path)
            task = queue["tasks"][0]
            readiness = {"ready_centers": ["codex", "claude"], "centers": {}}

            baseline = plan_next_experiment(queue_path, experiments_path, readiness)
            record_experiment_run(
                experiments_path,
                experiment_id=baseline["run"]["experiment_id"],
                task_fingerprint=task["task_fingerprint"],
                center="claude",
                variant="baseline",
                input_tokens=100,
                output_tokens=20,
            )
            harness = plan_next_experiment(queue_path, experiments_path, readiness)

        self.assertEqual("claude", baseline["run"]["center"])
        self.assertEqual("baseline", baseline["run"]["variant"])
        self.assertEqual("raw_repo", baseline["run"]["context_mode"])
        self.assertEqual("harness", harness["run"]["variant"])
        self.assertEqual("compact_harness", harness["run"]["context_mode"])

    def test_antigravity_plan_declares_manual_usage_ingestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.json"
            init_experiment_queue(queue_path)

            plan = plan_next_experiment(
                queue_path,
                Path(tmp) / "experiments.jsonl",
                {"ready_centers": ["antigravity"], "centers": {}},
            )

        self.assertEqual("manual", plan["run"]["usage_ingestion"])

    def test_builds_dry_run_claude_command_blueprint_with_schema_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = {
                "experiment_id": "harness-architecture-summary-v1:claude",
                "task_id": "harness-architecture-summary-v1",
                "task_fingerprint": "abc123",
                "center": "claude",
                "variant": "baseline",
                "context_mode": "raw_repo",
                "usage_ingestion": "claude_json",
                "prompt": "summarize",
                "output_schema": {"type": "object"},
            }

            blueprint = build_experiment_blueprint(root, run)

        self.assertFalse(blueprint["execute"])
        self.assertEqual("claude", blueprint["center"])
        self.assertIn("sonnet", blueprint["command"])
        self.assertNotIn("--tools", blueprint["command"])
        self.assertIn("--output-format", blueprint["command"])
        self.assertIn("--json-schema", blueprint["command"])
        self.assertTrue(blueprint["prompt_path"].endswith("prompt.txt"))
        self.assertTrue(blueprint["raw_output_path"].endswith("raw-output.json"))

    def test_builds_codex_and_antigravity_blueprints_without_claiming_auto_antigravity_usage(self):
        codex = build_experiment_blueprint(
            Path("/tmp/harness"),
            {"experiment_id": "task:codex", "center": "codex", "variant": "harness", "prompt": "p", "output_schema": {}},
        )
        antigravity = build_experiment_blueprint(
            Path("/tmp/harness"),
            {"experiment_id": "task:antigravity", "center": "antigravity", "variant": "baseline", "prompt": "p", "output_schema": {}},
        )

        self.assertEqual(["codex", "exec", "--json"], codex["command"][:3])
        self.assertEqual(["agy", "--print"], antigravity["command"][:2])
        self.assertEqual("manual", antigravity["usage_ingestion"])
        self.assertEqual("quality_only", antigravity["measurement_mode"])

    def test_prepares_manifest_prompt_and_schema_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = {
                "experiment_id": "task:claude",
                "task_fingerprint": "abc123",
                "center": "claude",
                "variant": "baseline",
                "context_mode": "raw_repo",
                "prompt": "summarize",
                "output_schema": {"type": "object"},
                "quality_rules": ["citation_count=5"],
            }

            manifest = prepare_experiment_run(root, run)

            manifest_path = Path(manifest["manifest_path"])
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(Path(manifest["prompt_path"]).is_file())
            self.assertTrue(Path(manifest["schema_path"]).is_file())
            self.assertFalse(manifest["execute"])
            self.assertEqual("REVIEW", manifest["command_policy"]["verdict"])
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("task:claude", loaded["experiment_id"])
            self.assertEqual(["citation_count=5"], loaded["quality_rules"])
