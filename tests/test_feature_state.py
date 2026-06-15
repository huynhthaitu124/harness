import tempfile
import unittest
from pathlib import Path

from harness_core.feature_state import (
    FeatureStateError,
    complete_feature,
    init_feature_list,
    next_feature,
)


class FeatureStateTests(unittest.TestCase):
    def test_initializes_features_as_default_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_list.json"

            init_feature_list(path, ["Build router", "Add evaluator"])

            feature = next_feature(path)
            self.assertEqual(feature["title"], "Build router")
            self.assertFalse(feature["passes"])
            self.assertEqual(feature["status"], "pending")

    def test_cannot_complete_feature_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_list.json"
            init_feature_list(path, ["Build router"])

            with self.assertRaises(FeatureStateError):
                complete_feature(path, 1, evidence=[])

    def test_completes_feature_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feature_list.json"
            init_feature_list(path, ["Build router"])

            complete_feature(path, 1, evidence=["unit tests passed"])

            self.assertIsNone(next_feature(path))


if __name__ == "__main__":
    unittest.main()
