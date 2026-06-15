import tempfile
import unittest
from pathlib import Path

from harness_core.capability_scaffold import scaffold_capability


class CapabilityScaffoldTests(unittest.TestCase):
    def test_scaffolds_skill_and_tool_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = scaffold_capability(Path(tmp), "context-auditor", "Audit context packs before cloud use")

            self.assertTrue(Path(result["skill_path"]).exists())
            self.assertTrue(Path(result["tool_spec_path"]).exists())
            self.assertIn("context-auditor", Path(result["skill_path"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
