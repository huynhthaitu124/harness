import unittest

from harness_core.output_compactor import compact_tool_output


class OutputCompactorTests(unittest.TestCase):
    def test_deduplicates_repeated_warnings_with_large_savings(self):
        text = ("WARN state db discrepancy\n" * 100) + '{"type":"turn.failed","error":{"message":"usage limit"}}\n'

        result = compact_tool_output(text, max_chars=2000)

        self.assertIn("repeated 100 times", result["output"])
        self.assertIn("turn.failed", result["output"])
        self.assertGreater(result["savings_percent"], 80)

    def test_keeps_high_signal_json_and_tail(self):
        text = "start\n" + "noise\n" * 50 + '{"type":"error","message":"quota"}\nfinal status\n'

        result = compact_tool_output(text, max_chars=300)

        self.assertIn('"type":"error"', result["output"])
        self.assertIn("final status", result["output"])

    def test_respects_character_cap(self):
        text = "\n".join(f"unique line {index}" for index in range(1000))

        result = compact_tool_output(text, max_chars=500)

        self.assertLessEqual(result["compact_chars"], 500)
        self.assertGreater(result["omitted_lines"], 0)

    def test_deduplicates_timestamped_warnings_and_keeps_critical_error(self):
        warnings = "".join(
            f"2026-06-14T17:44:{index:02d}.000Z WARN codex_rollout: state db discrepancy\n"
            for index in range(30)
        )
        text = warnings + '{"type":"error","message":"usage limit"}\n'

        result = compact_tool_output(text, max_chars=500)

        self.assertIn("repeated 30 times", result["output"])
        self.assertIn("usage limit", result["output"])


if __name__ == "__main__":
    unittest.main()
