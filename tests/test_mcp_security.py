import unittest

from harness_core.mcp_security import audit_mcp_security


class McpSecurityTests(unittest.TestCase):
    def test_passes_when_shell_execution_is_absent_and_command_policy_exists(self):
        report = audit_mcp_security(
            server_text="subprocess.run([str(command)], timeout=15)",
            tools=[
                {"name": "harness_validate_command", "description": "Validate commands"},
                {"name": "harness_build_experiment_blueprint", "description": "Build a non-executing command blueprint"},
            ],
        )

        self.assertEqual("PASS", report["verdict"])
        self.assertEqual([], report["failures"])

    def test_fails_when_shell_true_is_present(self):
        report = audit_mcp_security(
            server_text="subprocess.run(command, shell=True)",
            tools=[{"name": "harness_validate_command", "description": "Validate commands"}],
        )

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("shell_true_detected", report["failures"])

    def test_fails_when_command_policy_tool_is_missing(self):
        report = audit_mcp_security(server_text="subprocess.run([cmd])", tools=[])

        self.assertIn("missing_command_policy_tool", report["failures"])

    def test_fails_when_blueprint_tool_can_be_mistaken_for_execution(self):
        report = audit_mcp_security(
            server_text="subprocess.run([cmd])",
            tools=[
                {"name": "harness_validate_command", "description": "Validate commands"},
                {"name": "harness_build_experiment_blueprint", "description": "Build command"},
            ],
        )

        self.assertIn("blueprint_not_marked_non_executing", report["failures"])


if __name__ == "__main__":
    unittest.main()
