import unittest

from harness_core.local_capabilities import choose_embedding_model


class LocalCapabilitiesTests(unittest.TestCase):
    def test_prefers_qwen_embedding_when_installed(self):
        choice = choose_embedding_model(["all-minilm:latest", "qwen3-embedding:latest", "embeddinggemma"])

        self.assertEqual("qwen3-embedding", choice["model"])
        self.assertTrue(choice["installed"])

    def test_falls_back_to_embeddinggemma_before_all_minilm(self):
        choice = choose_embedding_model(["all-minilm:latest", "embeddinggemma:latest"])

        self.assertEqual("embeddinggemma", choice["model"])

    def test_requested_model_is_respected(self):
        choice = choose_embedding_model(["embeddinggemma"], requested_model="all-minilm")

        self.assertEqual("all-minilm", choice["model"])
        self.assertFalse(choice["installed"])


if __name__ == "__main__":
    unittest.main()
