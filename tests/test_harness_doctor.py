import json
import tempfile
import unittest
from pathlib import Path

from harness_core.harness_doctor import run_harness_doctor


class HarnessDoctorTests(unittest.TestCase):
    def test_flags_documented_script_that_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Run `./scripts/harness-vanished`.\n", encoding="utf-8")
            (root / "rules").mkdir()
            (root / "scripts").mkdir()
            (root / "harness_mcp").mkdir()
            (root / "harness_mcp" / "server.py").write_text("TOOLS = []\n", encoding="utf-8")

            report = run_harness_doctor(root)

        self.assertFalse(report["ok"])
        self.assertIn("harness-vanished", json.dumps(report))
        self.assertIn("missing_script", json.dumps(report))

    def test_flags_mcp_tool_that_is_not_documented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Documented: `harness_route_task`.\n", encoding="utf-8")
            (root / "rules").mkdir()
            (root / "scripts").mkdir()
            (root / "harness_mcp").mkdir()
            (root / "harness_mcp" / "server.py").write_text(
                "TOOLS = [\n"
                "    {'name': 'harness_route_task'},\n"
                "    {'name': 'harness_ghost_tool'},\n"
                "]\n",
                encoding="utf-8",
            )

            report = run_harness_doctor(root)

        self.assertTrue(report["ok"])
        self.assertIn("undocumented_tool", json.dumps(report))
        self.assertIn("harness_ghost_tool", json.dumps(report))

    def test_current_harness_has_no_doctor_errors(self):
        report = run_harness_doctor(Path(__file__).resolve().parents[1])

        self.assertTrue(report["ok"], json.dumps(report["issues"], indent=2))


if __name__ == "__main__":
    unittest.main()
