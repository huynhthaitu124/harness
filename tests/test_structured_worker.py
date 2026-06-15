import unittest

from harness_core.structured_worker import plan_structured_local_worker


class StructuredWorkerTests(unittest.TestCase):
    def test_plans_ollama_structured_output_when_gate_allows(self):
        plan = plan_structured_local_worker(
            "Summarize search results",
            machine={"swap_used_mb": 512, "swap_total_mb": 8192, "memory_free_percent": 55},
            task_complexity="light",
            schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        )

        self.assertTrue(plan["use_ollama"])
        self.assertEqual("structured_ollama", plan["mode"])
        self.assertEqual("json_schema", plan["format"]["type"])
        self.assertIn("Respond only with JSON", plan["prompt"])
        self.assertIn("ollama", plan["command"])

    def test_falls_back_when_local_gate_blocks_complex_work(self):
        plan = plan_structured_local_worker(
            "Summarize a large repository",
            machine={"swap_used_mb": 7600, "swap_total_mb": 8192, "memory_free_percent": 45},
            task_complexity="complex",
            schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        )

        self.assertFalse(plan["use_ollama"])
        self.assertEqual("extractive", plan["mode"])
        self.assertNotIn("command", plan)


if __name__ == "__main__":
    unittest.main()
