import tempfile
import unittest
from pathlib import Path

from harness_core.project_init import init_project_harness


class ProjectInitTests(unittest.TestCase):
    def test_creates_initializer_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = init_project_harness(root, ["Add login", "Add tests"])

            self.assertTrue((root / "init.sh").exists())
            self.assertTrue((root / "feature_list.json").exists())
            self.assertTrue((root / "production_artifacts" / "handoffs" / "README.md").exists())
            self.assertEqual(result["feature_count"], 2)


if __name__ == "__main__":
    unittest.main()
