import tempfile
import unittest
from pathlib import Path

from harness_core.hybrid_retrieval import build_hybrid_context_pack, retrieve_hybrid_chunks


class HybridRetrievalTests(unittest.TestCase):
    def test_symbol_and_path_boost_rank_specific_code_above_term_spam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth_service.py").write_text(
                "def rotate_token(user):\n    return user.token.rotate()\n",
                encoding="utf-8",
            )
            (root / "notes.txt").write_text("token token token token rotate documentation\n", encoding="utf-8")

            chunks = retrieve_hybrid_chunks(root, "rotate_token auth service", top_k=2, chunk_lines=20)

        self.assertEqual("auth_service.py", chunks[0]["path"])
        self.assertIn("rotate_token", chunks[0]["symbol"])

    def test_diversity_prefers_multiple_files_before_second_chunk_from_same_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "large.py").write_text(("auth token login\n" * 80), encoding="utf-8")
            (root / "secondary.py").write_text("auth token helper\n", encoding="utf-8")

            chunks = retrieve_hybrid_chunks(root, "auth token", top_k=2, chunk_lines=10, overlap_lines=2)

        self.assertEqual(2, len({chunk["path"] for chunk in chunks}))

    def test_pack_includes_line_ranges_and_score_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text("def login(token):\n    return bool(token)\n", encoding="utf-8")

            pack = build_hybrid_context_pack(root, "login token", top_k=1)

        self.assertIn("lines: 1-2", pack)
        self.assertIn("bm25_score:", pack)
        self.assertIn("path_symbol_boost:", pack)

    def test_chunk_before_first_symbol_is_labeled_file_top(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module.py").write_text(
                "import os\nimport sys\n\n\n\ndef later_function():\n    return os.getcwd()\n",
                encoding="utf-8",
            )

            chunks = retrieve_hybrid_chunks(root, "import os", top_k=1, chunk_lines=3, overlap_lines=0)

        self.assertEqual("(file top)", chunks[0]["symbol"])


if __name__ == "__main__":
    unittest.main()
