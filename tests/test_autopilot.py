import unittest

from harness_core.autopilot import plan_next_growth_action


class AutopilotTests(unittest.TestCase):
    def test_integrity_failure_has_highest_priority(self):
        plan = plan_next_growth_action(
            doctor={"ok": False, "issues": [{"code": "missing_script"}]},
            readiness={"ready_centers": ["codex"]},
            research={"due_count": 2, "changed_count": 1},
            retrieval_eval={"verdict": "NEEDS_WORK"},
            pending_feature={"id": 1, "description": "Add cache"},
        )

        self.assertEqual("repair_integrity", plan["action"])
        self.assertEqual("codex", plan["center"])

    def test_retrieval_regression_precedes_research_refresh(self):
        plan = plan_next_growth_action(
            doctor={"ok": True, "issues": []},
            readiness={"ready_centers": ["codex", "antigravity"]},
            research={"due_count": 2, "changed_count": 1},
            retrieval_eval={"verdict": "NEEDS_WORK", "reasons": ["mrr_below_threshold"]},
            pending_feature=None,
        )

        self.assertEqual("repair_retrieval", plan["action"])

    def test_changed_research_generates_review_action(self):
        plan = plan_next_growth_action(
            doctor={"ok": True, "issues": []},
            readiness={"ready_centers": ["antigravity"]},
            research={"due_count": 0, "changed_count": 2, "changed": [{"title": "MCP"}]},
            retrieval_eval={"verdict": "PASS"},
            pending_feature=None,
        )

        self.assertEqual("review_changed_sources", plan["action"])
        self.assertEqual("antigravity", plan["center"])
        self.assertTrue(plan["use_rag_first"])

    def test_token_experiment_plan_precedes_pending_feature_when_ready(self):
        plan = plan_next_growth_action(
            doctor={"ok": True, "issues": []},
            readiness={"ready_centers": ["claude"]},
            research={"due_count": 0, "changed_count": 0},
            retrieval_eval={"verdict": "PASS"},
            pending_feature={"id": 2, "description": "Add report"},
            experiment_plan={
                "verdict": "READY",
                "run": {
                    "center": "claude",
                    "variant": "baseline",
                    "experiment_id": "harness-architecture-summary-v1:claude",
                    "context_mode": "raw_repo",
                },
            },
        )

        self.assertEqual("run_token_experiment", plan["action"])
        self.assertEqual("claude", plan["center"])
        self.assertIn("record_experiment_run", plan["workflow"])
        self.assertEqual("baseline", plan["experiment_run"]["variant"])

    def test_no_ready_center_selects_local_maintenance(self):
        plan = plan_next_growth_action(
            doctor={"ok": True, "issues": []},
            readiness={"ready_centers": []},
            research={"due_count": 0, "changed_count": 0},
            retrieval_eval={"verdict": "PASS"},
            pending_feature={"id": 2, "description": "Add report"},
        )

        self.assertEqual("local_maintenance", plan["action"])
        self.assertEqual("local", plan["center"])
        self.assertNotIn("delegate", plan["workflow"])


if __name__ == "__main__":
    unittest.main()
