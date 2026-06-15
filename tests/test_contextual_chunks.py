import tempfile
import unittest
from pathlib import Path

from harness_core.contextual_chunks import build_contextual_chunks, build_contextual_context_pack


class ContextualChunksTests(unittest.TestCase):
    def test_builds_chunks_with_path_query_and_symbol_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text(
                "def login_user(token):\n"
                "    if not token:\n"
                "        return False\n"
                "    return token.startswith('sk-')\n",
                encoding="utf-8",
            )

            chunks = build_contextual_chunks(root, query="login token", max_chars_per_chunk=80)

        self.assertEqual(1, len(chunks))
        chunk = chunks[0]
        self.assertEqual("auth.py", chunk["path"])
        self.assertEqual("def login_user(token):", chunk["symbol"])
        self.assertIn("query: login token", chunk["context"])
        self.assertIn("path: auth.py", chunk["context"])
        self.assertIn("def login_user", chunk["text"])

    def test_contextual_pack_uses_bounded_relevant_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text("login token\n" * 80, encoding="utf-8")
            (root / "billing.py").write_text("invoice payment\n" * 80, encoding="utf-8")

            pack = build_contextual_context_pack(root, query="login", top_k=1, max_chars_per_chunk=120)

        self.assertIn("# Contextual context pack", pack)
        self.assertIn("## auth.py", pack)
        self.assertNotIn("## billing.py", pack)


if __name__ == "__main__":
    unittest.main()
