import unittest

from harness_mcp.server import dispatch


class McpPromptsTests(unittest.TestCase):
    def test_lists_workflow_prompts(self):
        response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}})

        names = [prompt["name"] for prompt in response["result"]["prompts"]]
        self.assertIn("self_growth_cycle", names)

    def test_gets_self_growth_prompt(self):
        response = dispatch(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "prompts/get",
                "params": {"name": "self_growth_cycle", "arguments": {"topic": "RAG"}},
            }
        )

        self.assertIn("RAG", response["result"]["messages"][0]["content"]["text"])


if __name__ == "__main__":
    unittest.main()
