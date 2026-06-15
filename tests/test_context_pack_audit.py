import tempfile
import unittest
from pathlib import Path

from harness_core.context_pack_audit import audit_context_packs


class ContextPackAuditTests(unittest.TestCase):
    def test_passes_source_cited_pack_under_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_dir = root / "production_artifacts" / "context_packs"
            pack_dir.mkdir(parents=True)
            (pack_dir / "pack.md").write_text(
                "# Hybrid context pack\nquery: auth\nroot: .\n\n## app.py\nlines: 1-4\nsymbol: def auth\n```text\ncode\n```\n",
                encoding="utf-8",
            )

            report = audit_context_packs(root, max_chars_per_pack=1000)

        self.assertEqual("PASS", report["verdict"])
        self.assertEqual([], report["failures"])
        self.assertEqual(1, report["pack_count"])

    def test_fails_pack_over_budget_and_missing_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_dir = root / "production_artifacts" / "context_packs"
            pack_dir.mkdir(parents=True)
            (pack_dir / "bad.md").write_text("no cited sections\n" + ("x" * 1200), encoding="utf-8")

            report = audit_context_packs(root, max_chars_per_pack=1000)

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("over_budget:bad.md", report["failures"])
        self.assertIn("missing_section_heading:bad.md", report["failures"])
        self.assertIn("missing_code_fence:bad.md", report["failures"])

    def test_accepts_indexed_pack_heading_as_path_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_dir = root / "production_artifacts" / "context_packs"
            pack_dir.mkdir(parents=True)
            (pack_dir / "indexed.md").write_text(
                "# Indexed context pack\nquery: q\nroot: .\n\n## src/app.py\nscore: 1.0\n```text\ncode\n```\n",
                encoding="utf-8",
            )

            report = audit_context_packs(root, max_chars_per_pack=1000)

        self.assertEqual("PASS", report["verdict"])


if __name__ == "__main__":
    unittest.main()
