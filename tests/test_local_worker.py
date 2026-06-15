import unittest

from harness_core.local_worker import plan_local_worker


class LocalWorkerTests(unittest.TestCase):
    def test_plans_extract_only_when_gate_blocks_model(self):
        plan = plan_local_worker(
            "summarize indexed context",
            machine={"swap_used_mb": 7600, "swap_total_mb": 8192, "memory_free_percent": 45},
            task_complexity="complex",
        )

        self.assertEqual(plan["mode"], "extractive")
        self.assertFalse(plan["use_ollama"])

    def test_plans_ollama_for_light_work_when_gate_allows(self):
        plan = plan_local_worker(
            "summarize one file",
            machine={"swap_used_mb": 400, "swap_total_mb": 8192, "memory_free_percent": 60},
            task_complexity="light",
            model="qwen35-codex-local",
        )

        self.assertEqual(plan["mode"], "ollama")
        self.assertTrue(plan["use_ollama"])
        self.assertIn("qwen35-codex-local", plan["command"])


if __name__ == "__main__":
    unittest.main()
