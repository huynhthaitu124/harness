import unittest

from harness_core.readiness import build_readiness_report
from harness_core.router import default_state


class ReadinessTests(unittest.TestCase):
    def test_reports_quota_limited_center_unavailable(self):
        state = default_state()
        state["quotas"]["claude"].update(
            {"available": False, "remaining_percent": 0, "reset_hint": "1:50am", "last_error": "session limit"}
        )
        probes = {center: {"installed": True, "harness_connected": True} for center in ("codex", "claude", "antigravity")}

        report = build_readiness_report(state, probes=probes)

        self.assertEqual("unavailable", report["centers"]["claude"]["status"])
        self.assertIn("1:50am", " ".join(report["centers"]["claude"]["reasons"]))

    def test_reports_recent_worker_failure_as_degraded(self):
        state = default_state()
        state["quotas"]["antigravity"]["consecutive_failures"] = 1
        probes = {center: {"installed": True, "harness_connected": True} for center in ("codex", "claude", "antigravity")}

        report = build_readiness_report(state, probes=probes)

        self.assertEqual("degraded", report["centers"]["antigravity"]["status"])

    def test_local_worker_uses_live_gate(self):
        state = default_state()
        probes = {center: {"installed": True, "harness_connected": True} for center in ("codex", "claude", "antigravity")}

        report = build_readiness_report(
            state,
            probes=probes,
            local_probe={"installed": True, "model_loaded": False},
            machine={"swap_used_mb": 12600, "swap_total_mb": 13312, "memory_free_percent": 36},
        )

        self.assertEqual("blocked", report["local_worker"]["status"])


if __name__ == "__main__":
    unittest.main()
