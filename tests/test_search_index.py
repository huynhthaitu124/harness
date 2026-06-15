import tempfile
import unittest
from pathlib import Path

from harness_core.search_index import build_index, build_indexed_context_pack, search_index


class SearchIndexTests(unittest.TestCase):
    def test_builds_and_searches_repo_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / ".index.json"
            (root / "auth.py").write_text("def login():\n    return 'token'\n", encoding="utf-8")
            (root / "billing.py").write_text("def invoice():\n    return 'paid'\n", encoding="utf-8")

            build_index(root, index)
            results = search_index(index, "login token")

            self.assertEqual(results[0]["path"], "auth.py")
            self.assertGreater(results[0]["score"], 0)

    def test_builds_indexed_context_pack_from_search_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / ".index.json"
            (root / "auth.py").write_text("def login():\n    return 'token'\n" * 40, encoding="utf-8")
            (root / "billing.py").write_text("def invoice():\n    return 'paid'\n" * 40, encoding="utf-8")
            build_index(root, index)

            pack = build_indexed_context_pack(root, index, "login token", max_chars_per_file=200)

            self.assertIn("auth.py", pack)
            self.assertNotIn("billing.py", pack)

    def test_index_skips_generated_production_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / ".index.json"
            (root / "src.py").write_text("real source token", encoding="utf-8")
            artifact = root / "production_artifacts" / "indexes"
            artifact.mkdir(parents=True)
            (artifact / "old.json").write_text("token " * 100, encoding="utf-8")

            build_index(root, index)
            results = search_index(index, "token")

            self.assertEqual(results[0]["path"], "src.py")


if __name__ == "__main__":
    unittest.main()
