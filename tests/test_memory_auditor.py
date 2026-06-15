import tempfile
import unittest
from pathlib import Path

from harness_core.memory_auditor import audit_handoffs


class MemoryAuditorTests(unittest.TestCase):
    def test_flags_handoff_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoffs = root / "production_artifacts" / "handoffs"
            handoffs.mkdir(parents=True)
            (handoffs / "weak.md").write_text("# Weak\n\nDone maybe.\n", encoding="utf-8")

            report = audit_handoffs(root)

            self.assertEqual(report["issues"][0]["type"], "missing_evidence")

    def test_accepts_handoff_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoffs = root / "production_artifacts" / "handoffs"
            handoffs.mkdir(parents=True)
            (handoffs / "strong.md").write_text("# Strong\n\nEvidence: tests passed.\n", encoding="utf-8")

            report = audit_handoffs(root)

            self.assertEqual(report["issue_count"], 0)


if __name__ == "__main__":
    unittest.main()
