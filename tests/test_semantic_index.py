import tempfile
import unittest
from pathlib import Path

from harness_core.semantic_index import build_semantic_index, plan_semantic_index, search_semantic_index


def keyword_embedder(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        lowered = text.lower()
        vectors.append(
            [
                float(lowered.count("login") + lowered.count("token")),
                float(lowered.count("invoice") + lowered.count("payment")),
            ]
        )
    return vectors


class SemanticIndexTests(unittest.TestCase):
    def test_builds_and_searches_semantic_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.txt").write_text("login token authentication", encoding="utf-8")
            (root / "billing.txt").write_text("invoice payment settlement", encoding="utf-8")
            index = Path(tmp) / "semantic.json"
            build_semantic_index(root, index, embedder=keyword_embedder, model="fake")

            results = search_semantic_index(index, "login token", embedder=keyword_embedder, top_k=1)

        self.assertEqual("auth.txt", results[0]["path"])
        self.assertGreater(results[0]["score"], 0.9)

    def test_reuses_cached_vectors_for_unchanged_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.txt").write_text("login token", encoding="utf-8")
            index = Path(tmp) / "semantic.json"
            calls = []

            def counted(texts: list[str]) -> list[list[float]]:
                calls.append(list(texts))
                return keyword_embedder(texts)

            first = build_semantic_index(root, index, embedder=counted, model="fake")
            second = build_semantic_index(root, index, embedder=counted, model="fake")

        self.assertEqual(1, first["embedded_count"])
        self.assertEqual(0, second["embedded_count"])
        self.assertEqual(1, second["reused_count"])
        self.assertEqual(1, len(calls))

    def test_high_swap_blocks_local_embedding_plan(self):
        plan = plan_semantic_index(
            machine={"swap_used_mb": 12610, "swap_total_mb": 13312, "memory_free_percent": 36},
            installed_models=[],
        )

        self.assertFalse(plan["use_ollama"])
        self.assertEqual("hybrid_lexical", plan["mode"])
        self.assertNotIn("pull_command", plan)


if __name__ == "__main__":
    unittest.main()
