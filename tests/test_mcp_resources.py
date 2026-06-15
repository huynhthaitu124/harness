import unittest

from harness_mcp.server import dispatch


class McpResourcesTests(unittest.TestCase):
    def test_lists_harness_resources(self):
        response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}})

        uris = [resource["uri"] for resource in response["result"]["resources"]]
        self.assertIn("harness://state", uris)
        self.assertIn("harness://rules/10-context-economy.md", uris)

    def test_reads_harness_state_resource(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {"uri": "harness://state"},
            }
        )

        self.assertIn("preferred_center", response["result"]["contents"][0]["text"])


if __name__ == "__main__":
    unittest.main()
