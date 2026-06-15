import unittest
from pathlib import Path

from harness_core.mcp_conformance import run_mcp_conformance


class McpConformanceTests(unittest.TestCase):
    def test_real_harness_server_passes_protocol_smoke(self):
        root = Path(__file__).resolve().parents[1]

        report = run_mcp_conformance(root / "scripts" / "harness-mcp-server", cwd=root)

        self.assertEqual("PASS", report["verdict"])
        self.assertGreater(report["tool_count"], 40)
        self.assertGreaterEqual(report["resource_count"], 1)
        self.assertGreaterEqual(report["prompt_count"], 3)
        self.assertEqual([], report["duplicate_tools"])


if __name__ == "__main__":
    unittest.main()
