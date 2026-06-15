import tempfile
import unittest
from pathlib import Path

from harness_core.agent_rag import build_agent_rag_pack
from harness_core.memory_index import record_memory
from harness_core.router import default_state, save_state


class AgentRagPackTests(unittest.TestCase):
    def test_builds_shared_rag_pack_with_all_agent_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness").mkdir()
            save_state(root / ".harness" / "state.json", default_state())
            (root / "auth.py").write_text("def login():\n    return 'token'\n" * 50, encoding="utf-8")
            record_memory(
                root / ".harness" / "memory.jsonl",
                content="Auth token decisions live in auth.py",
                source="handoff.md",
                kind="decision",
            )

            report = build_agent_rag_pack(root, "fix login token handling", center="claude")
            pack_path = Path(report["context_pack_path"])
            content = pack_path.read_text(encoding="utf-8")

            self.assertEqual("claude", report["center"])
            self.assertIn("memory_pack", report["sources"])
            self.assertIn("hybrid_rag", report["sources"])
            self.assertIn("codex exec", content)
            self.assertIn("claude -p", content)
            self.assertIn("--model sonnet", content)
            self.assertIn("agy --print", content)
            self.assertIn("/api/chat", content)
            self.assertNotIn("'$(cat", content)
            self.assertIn('cat "$PACK"', content)
            self.assertIn("## Retrieval Payload", content)

    def test_project_center_uses_state_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness").mkdir()
            state = default_state()
            state["preferred_center"] = "antigravity"
            save_state(root / ".harness" / "state.json", state)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")

            report = build_agent_rag_pack(root, "summarize app", center="project")

        self.assertEqual("antigravity", report["center"])


if __name__ == "__main__":
    unittest.main()
