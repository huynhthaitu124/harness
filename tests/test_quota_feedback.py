import unittest

from harness_core.quota_feedback import apply_worker_feedback
from harness_core.router import default_state


class QuotaFeedbackTests(unittest.TestCase):
    def test_marks_center_unavailable_on_session_limit(self):
        state = default_state()

        updated = apply_worker_feedback(
            state,
            center="claude",
            returncode=1,
            output="You've hit your session limit - resets 1:50am (Asia/Saigon)",
        )

        quota = updated["quotas"]["claude"]
        self.assertFalse(quota["available"])
        self.assertEqual(0, quota["remaining_percent"])
        self.assertIn("1:50am", quota["reset_hint"])

    def test_extracts_try_again_reset_hint(self):
        state = default_state()

        updated = apply_worker_feedback(
            state,
            center="codex",
            returncode=1,
            output="You've hit your usage limit. Please try again at 5:10 AM.",
        )

        self.assertFalse(updated["quotas"]["codex"]["available"])
        self.assertEqual("5:10 AM", updated["quotas"]["codex"]["reset_hint"])

    def test_success_restores_center_availability(self):
        state = default_state()
        state["quotas"]["claude"]["available"] = False
        state["quotas"]["claude"]["remaining_percent"] = 0

        updated = apply_worker_feedback(state, center="claude", returncode=0, output="ok")

        self.assertTrue(updated["quotas"]["claude"]["available"])
        self.assertNotIn("remaining_percent", updated["quotas"]["claude"])

    def test_transient_failure_increments_failure_counter(self):
        state = default_state()

        updated = apply_worker_feedback(
            state,
            center="antigravity",
            returncode=124,
            output="worker timed out after 120s",
        )

        self.assertEqual(1, updated["quotas"]["antigravity"]["consecutive_failures"])
        recovered = apply_worker_feedback(updated, center="antigravity", returncode=0, output="ok")
        self.assertNotIn("consecutive_failures", recovered["quotas"]["antigravity"])


if __name__ == "__main__":
    unittest.main()
