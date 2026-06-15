import unittest

from harness_core.local_rag_pipeline import execute_local_rag_pipeline, plan_local_rag_pipeline


class LocalRagPipelineTests(unittest.TestCase):
    def test_high_swap_returns_retrieval_only_fallback(self):
        plan = plan_local_rag_pipeline(
            "analyze architecture",
            chunk_count=12,
            machine={"swap_used_mb": 12600, "swap_total_mb": 13312, "memory_free_percent": 36},
            installed_models=["qwen35-codex-local:latest"],
        )

        self.assertEqual("retrieval_only", plan["mode"])
        self.assertFalse(plan["use_ollama"])
        self.assertEqual(["hybrid_retrieve", "build_context_pack"], plan["stages"])

    def test_healthy_machine_plans_structured_map_reduce_verify(self):
        plan = plan_local_rag_pipeline(
            "analyze architecture",
            chunk_count=12,
            machine={"swap_used_mb": 200, "swap_total_mb": 8192, "memory_free_percent": 60},
            installed_models=["qwen35-codex-local:latest"],
        )

        self.assertTrue(plan["use_ollama"])
        self.assertEqual("structured_map_reduce", plan["mode"])
        self.assertEqual(1, plan["max_parallel"])
        self.assertIn("verify", plan["stages"])
        self.assertEqual(3, plan["map_batch_count"])

    def test_executor_uses_structured_map_reduce_contracts(self):
        plan = {
            "mode": "structured_map_reduce",
            "use_ollama": True,
            "map_batch_size": 2,
            "output_schema": {"required": ["summary", "evidence"]},
        }
        calls = []

        def runner(stage, payload, schema):
            calls.append(stage)
            if stage == "map":
                return {"summary": f"mapped {len(payload['chunks'])}", "evidence": ["chunk"]}
            return {"summary": "final", "evidence": ["chunk"]}

        result = execute_local_rag_pipeline(plan, ["a", "b", "c"], runner=runner)

        self.assertEqual(["map", "map", "reduce"], calls)
        self.assertEqual("final", result["result"]["summary"])
        self.assertEqual("PASS", result["verification"]["verdict"])


if __name__ == "__main__":
    unittest.main()
