import unittest

from harness_core.health_suite import aggregate_health


class HealthSuiteTests(unittest.TestCase):
    def test_passes_core_gates_with_readiness_constraints(self):
        report = aggregate_health(
            tests={"passed": True, "count": 141},
            doctor={"ok": True, "issues": []},
            mcp={"verdict": "PASS"},
            retrieval={"verdict": "PASS", "recall_at_k": 1.0, "mrr": 0.9},
            research={"due_count": 0, "changed_count": 0},
            readiness={"ready_centers": [], "centers": {}},
            campaign={"verdict": "IN_PROGRESS"},
            experiments={"verdict": "INCOMPLETE", "missing_centers": ["codex", "claude", "antigravity"]},
            security={"verdict": "PASS", "warnings": []},
            context_packs={"verdict": "PASS", "failures": []},
        )

        self.assertEqual("PASS_WITH_CONSTRAINTS", report["verdict"])
        self.assertIn("no_ready_cloud_center", report["warnings"])
        self.assertIn("token_evidence_missing:claude,codex", report["warnings"])
        self.assertNotIn("token_evidence_missing:antigravity,claude,codex", report["warnings"])

    def test_default_fails_when_any_core_gate_fails(self):
        report = aggregate_health(
            tests={"passed": False, "count": 140},
            doctor={"ok": True, "issues": []},
            mcp={"verdict": "PASS"},
            retrieval={"verdict": "PASS"},
            research={"due_count": 0, "changed_count": 0},
            readiness={"ready_centers": ["codex"]},
            campaign={"verdict": "IN_PROGRESS"},
            experiments={"verdict": "PASS", "missing_centers": [], "non_saving_centers": []},
            security={"verdict": "PASS", "warnings": []},
            context_packs={"verdict": "PASS", "failures": []},
        )

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("tests_failed", report["failures"])

    def test_changed_research_is_warning_not_silent(self):
        report = aggregate_health(
            tests={"passed": True},
            doctor={"ok": True},
            mcp={"verdict": "PASS"},
            retrieval={"verdict": "PASS"},
            research={"due_count": 0, "changed_count": 2},
            readiness={"ready_centers": ["codex"]},
            campaign={"verdict": "IN_PROGRESS"},
            experiments={"verdict": "PASS", "missing_centers": [], "non_saving_centers": []},
            security={"verdict": "PASS", "warnings": []},
            context_packs={"verdict": "PASS", "failures": []},
        )

        self.assertIn("changed_research_sources:2", report["warnings"])

    def test_token_regression_is_never_hidden(self):
        report = aggregate_health(
            tests={"passed": True},
            doctor={"ok": True},
            mcp={"verdict": "PASS"},
            retrieval={"verdict": "PASS"},
            research={"due_count": 0, "changed_count": 0},
            readiness={"ready_centers": ["codex"]},
            campaign={"verdict": "PASS"},
            experiments={"verdict": "REGRESSION", "missing_centers": [], "non_saving_centers": ["claude"]},
            security={"verdict": "PASS", "warnings": []},
            context_packs={"verdict": "PASS", "failures": []},
        )

        self.assertEqual("PASS_WITH_CONSTRAINTS", report["verdict"])
        self.assertIn("token_regression:claude", report["warnings"])

    def test_security_failure_is_core_failure(self):
        report = aggregate_health(
            tests={"passed": True},
            doctor={"ok": True},
            mcp={"verdict": "PASS"},
            retrieval={"verdict": "PASS"},
            research={"due_count": 0, "changed_count": 0},
            readiness={"ready_centers": ["codex"]},
            campaign={"verdict": "PASS"},
            experiments={"verdict": "PASS", "missing_centers": [], "non_saving_centers": []},
            security={"verdict": "NEEDS_WORK", "failures": ["shell_true_detected"]},
            context_packs={"verdict": "PASS", "failures": []},
        )

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("mcp_security_failed", report["failures"])

    def test_context_pack_audit_failure_is_core_failure(self):
        report = aggregate_health(
            tests={"passed": True},
            doctor={"ok": True},
            mcp={"verdict": "PASS"},
            retrieval={"verdict": "PASS"},
            research={"due_count": 0, "changed_count": 0},
            readiness={"ready_centers": ["codex"]},
            campaign={"verdict": "PASS"},
            experiments={"verdict": "PASS", "missing_centers": [], "non_saving_centers": []},
            security={"verdict": "PASS", "warnings": []},
            context_packs={"verdict": "NEEDS_WORK", "failures": ["over_budget:bad.md"]},
        )

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("context_pack_audit_failed", report["failures"])


if __name__ == "__main__":
    unittest.main()
