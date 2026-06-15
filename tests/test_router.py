import json
import tempfile
import unittest
from pathlib import Path

from harness_core.router import choose_center, default_state, load_state, save_state


class RouterTests(unittest.TestCase):
    def test_prefers_user_selected_center_when_available(self):
        state = default_state()
        state["preferred_center"] = "antigravity"
        state["quotas"]["antigravity"]["available"] = True

        decision = choose_center("implement a UI refactor", state)

        self.assertEqual(decision["center"], "antigravity")
        self.assertIn("preferred center", decision["reasons"][0])

    def test_falls_back_when_preferred_center_unavailable(self):
        state = default_state()
        state["preferred_center"] = "codex"
        state["quotas"]["codex"]["available"] = False
        state["quotas"]["claude"]["available"] = True

        decision = choose_center("fix a small bug", state)

        self.assertEqual(decision["center"], "claude")
        self.assertTrue(any("unavailable" in reason for reason in decision["reasons"]))

    def test_research_heavy_tasks_require_rag_first(self):
        state = default_state()

        decision = choose_center("research this codebase and summarize the auth flow", state)

        self.assertTrue(decision["use_rag_first"])
        self.assertIn("rag_summarize", decision["workflow"])

    def test_codex_workflows_require_preflight_before_execution(self):
        state = default_state()
        state["preferred_center"] = "codex"

        decision = choose_center("fix a repo bug and inspect related code", state)

        self.assertEqual("codex", decision["center"])
        self.assertLess(decision["workflow"].index("codex_preflight"), decision["workflow"].index("codex_execute"))

    def test_auto_routing_uses_normalized_observed_usage(self):
        state = default_state()
        usage = {
            "by_center": {
                "codex": {"input_tokens": 80000, "output_tokens": 10000, "cost_usd": 0},
                "claude": {"input_tokens": 50000, "output_tokens": 5000, "cost_usd": 1.0},
                "antigravity": {"input_tokens": 10000, "output_tokens": 1000, "cost_usd": 0},
            }
        }

        decision = choose_center("answer a general architecture question", state, usage_summary=usage)

        self.assertEqual(decision["center"], "antigravity")
        self.assertIn("normalized observed usage", " ".join(decision["reasons"]))
        self.assertIn("routing_metrics", decision)

    def test_auto_routing_avoids_center_with_low_remaining_quota(self):
        state = default_state()
        state["quotas"]["antigravity"]["remaining_percent"] = 4
        usage = {
            "by_center": {
                "codex": {"input_tokens": 1000, "output_tokens": 100, "cost_usd": 0},
                "claude": {"input_tokens": 5000, "output_tokens": 500, "cost_usd": 0},
                "antigravity": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0},
            }
        }

        decision = choose_center("answer a general question", state, usage_summary=usage)

        self.assertNotEqual(decision["center"], "antigravity")
        self.assertIn("low remaining quota", " ".join(decision["reasons"]))

    def test_auto_routing_penalizes_recent_worker_failures(self):
        state = default_state()
        state["quotas"]["claude"]["available"] = False
        state["quotas"]["antigravity"]["consecutive_failures"] = 1
        usage = {
            "by_center": {
                "codex": {"input_tokens": 10000, "output_tokens": 1000, "cost_usd": 0},
                "antigravity": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0},
            }
        }

        decision = choose_center("research source freshness", state, usage_summary=usage)

        self.assertEqual("codex", decision["center"])
        self.assertGreater(decision["routing_metrics"]["antigravity"]["failure_penalty"], 0)

    def test_state_round_trips_as_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = default_state()
            state["preferred_center"] = "claude"

            save_state(path, state)
            loaded = load_state(path)

            self.assertEqual(loaded["preferred_center"], "claude")
            self.assertEqual(json.loads(path.read_text())["preferred_center"], "claude")


if __name__ == "__main__":
    unittest.main()
