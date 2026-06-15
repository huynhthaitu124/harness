import tempfile
import unittest
from pathlib import Path

from harness_core.research_refresh import default_research_registry_path, refresh_default_research


class ResearchRefreshTests(unittest.TestCase):
    def test_initializes_default_registry_and_writes_last_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = refresh_default_research(root, fetcher=lambda _: b"current", force=False)

            registry = default_research_registry_path(root)
            last_refresh = root / ".harness" / "research" / "last-refresh.json"
            registry_exists = registry.exists()
            last_refresh_exists = last_refresh.exists()

        self.assertIn("Codex", report["refresh"]["checked"][0]["title"])
        self.assertTrue(registry_exists)
        self.assertTrue(last_refresh_exists)
        self.assertEqual("no_update_needed", report["next_action"])


if __name__ == "__main__":
    unittest.main()
