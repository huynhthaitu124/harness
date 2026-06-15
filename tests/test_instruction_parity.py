import unittest
from pathlib import Path


class InstructionParityTests(unittest.TestCase):
    def test_all_centers_reference_core_token_saving_workflow(self):
        root = Path(__file__).resolve().parents[1]
        files = [
            root / "AGENTS.md",
            root / "CLAUDE.md",
            root / "antigravity-plugin" / "skills" / "harness-router" / "SKILL.md",
        ]
        required = [
            "harness-route",
            "harness-readiness",
            "harness-hybrid-context",
            "harness-experiment",
            "harness-handoff",
            "harness-compact-output",
            "harness-autopilot",
            "harness-campaign",
            "harness-local-pipeline",
            "harness-memory",
            "harness-command-policy",
            "harness-mcp-check",
            "harness-health",
            "harness-experiment-queue",
            "harness-experiment-quality",
            "harness-mcp-security",
            "harness-context-pack-audit",
            "harness-codex-preflight",
        ]

        for path in files:
            text = path.read_text(encoding="utf-8")
            for command in required:
                self.assertIn(command, text, f"{path.name} missing {command}")


if __name__ == "__main__":
    unittest.main()
