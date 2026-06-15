import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness_core.router import default_state, save_state

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "harness"


class HarnessCliProjectControlsTests(unittest.TestCase):
    def test_center_set_persists_per_project_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness").mkdir()
            save_state(root / ".harness" / "state.json", default_state())

            result = subprocess.run(
                [sys.executable, str(HARNESS), "center", "set", "claude", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )

            state = json.loads((root / ".harness" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("claude", state["preferred_center"])
        self.assertIn("claude", result.stdout)

    def test_rag_pack_command_writes_shared_agent_context_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness").mkdir()
            save_state(root / ".harness" / "state.json", default_state())
            (root / "billing.py").write_text("def invoice():\n    return 'paid'\n" * 20, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(HARNESS), "rag-pack", "summarize invoice flow", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )

            pack = root / ".harness" / "context_packs" / "last-rag-pack.md"
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(pack.exists())
            self.assertIn("codex exec", pack.read_text(encoding="utf-8"))
            self.assertIn("Context pack", result.stdout)

    def test_status_shows_local_model_and_rag_pack_without_project_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".harness" / "context_packs").mkdir(parents=True)
            save_state(root / ".harness" / "state.json", default_state())
            (root / ".harness" / "context_packs" / "last-rag-pack.md").write_text("# pack\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(HARNESS), "status", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Local LLM", result.stdout)
        self.assertIn("qwen3.5:9b", result.stdout)
        self.assertIn("RAG pack", result.stdout)


if __name__ == "__main__":
    unittest.main()
