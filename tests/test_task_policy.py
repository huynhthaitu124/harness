import unittest

from harness_core.task_policy import classify_harness_mode


class TaskPolicyTests(unittest.TestCase):
    def test_fast_mode_for_explicit_file(self):
        result = classify_harness_mode("fix typo in README.md")

        self.assertEqual("fast", result["mode"])
        self.assertFalse(result["harness_required"])

    def test_deep_mode_for_refactor(self):
        result = classify_harness_mode("refactor auth flow across the codebase")

        self.assertEqual("deep", result["mode"])
        self.assertTrue(result["harness_required"])

    def test_light_mode_by_default(self):
        result = classify_harness_mode("fix login behavior")

        self.assertEqual("light", result["mode"])
        self.assertFalse(result["harness_required"])


if __name__ == "__main__":
    unittest.main()
