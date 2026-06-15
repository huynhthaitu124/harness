import unittest

from harness_core.local_model_gate import local_model_decision


class LocalModelGateTests(unittest.TestCase):
    def test_blocks_complex_local_work_when_swap_is_high(self):
        decision = local_model_decision({"swap_used_mb": 7600, "swap_total_mb": 8192, "memory_free_percent": 45}, "complex")

        self.assertFalse(decision["allow"])
        self.assertIn("swap", decision["reasons"][0])

    def test_allows_light_local_work_when_memory_is_healthy(self):
        decision = local_model_decision({"swap_used_mb": 500, "swap_total_mb": 8192, "memory_free_percent": 60}, "light")

        self.assertTrue(decision["allow"])
        self.assertEqual(decision["max_context_tokens"], 8192)


if __name__ == "__main__":
    unittest.main()
