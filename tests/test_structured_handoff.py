import tempfile
import unittest
from pathlib import Path

from harness_core.structured_handoff import validate_structured_handoff, write_structured_handoff


class StructuredHandoffTests(unittest.TestCase):
    def test_writes_markdown_and_json_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "tests.txt"
            evidence.write_text("107 tests pass", encoding="utf-8")

            result = write_structured_handoff(
                root,
                title="Auth implementation",
                summary="Implemented auth flow",
                from_center="codex",
                to_center="claude",
                task_fingerprint="auth-v1",
                evidence=["tests.txt"],
            )

        self.assertTrue(Path(result["markdown_path"]).name.endswith(".md"))
        self.assertTrue(Path(result["manifest_path"]).name.endswith(".json"))

    def test_validation_default_fails_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = write_structured_handoff(
                root,
                title="Missing evidence",
                summary="Done",
                from_center="codex",
                to_center="antigravity",
                task_fingerprint="task-v1",
                evidence=["missing.txt"],
            )

            report = validate_structured_handoff(Path(result["manifest_path"]), root=root)

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("missing_evidence_file:missing.txt", report["missing"])

    def test_validation_passes_complete_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence.txt").write_text("pass", encoding="utf-8")
            (root / "context.md").write_text("compact context", encoding="utf-8")
            result = write_structured_handoff(
                root,
                title="Complete",
                summary="Ready for review",
                from_center="codex",
                to_center="claude",
                task_fingerprint="task-v1",
                evidence=["evidence.txt"],
                context_pack="context.md",
            )

            report = validate_structured_handoff(Path(result["manifest_path"]), root=root)

        self.assertEqual("PASS", report["verdict"])


if __name__ == "__main__":
    unittest.main()
