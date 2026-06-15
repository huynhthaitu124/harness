import tempfile
import unittest
from pathlib import Path

from harness_core.capability_scaffold import scaffold_capability
from harness_core.capability_registry import evaluate_capability, list_capabilities, promote_capability


class CapabilityRegistryTests(unittest.TestCase):
    def test_lists_scaffolded_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_capability(root, "memory-auditor", "Audit memory")
            scaffold_capability(root, "rag-upgrader", "Upgrade RAG")

            capabilities = list_capabilities(root)

        self.assertEqual([item["name"] for item in capabilities], ["memory-auditor", "rag-upgrader"])

    def test_capability_promotion_default_fails_without_tool_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scaffold_capability(root, "memory-auditor", "Audit memory")

            report = evaluate_capability(root, "memory-auditor", evidence=[])

        self.assertEqual("NEEDS_WORK", report["verdict"])
        self.assertIn("missing_mcp_tools", report["missing"])
        self.assertIn("missing_evidence", report["missing"])

    def test_promotes_capability_only_after_contract_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = scaffold_capability(root, "memory-auditor", "Audit memory")
            spec_path = Path(result["tool_spec_path"])
            import json

            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["mcp_tools"] = ["harness_audit_handoffs"]
            spec["documentation"] = ["README.md"]
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            (root / "README.md").write_text("memory auditor docs", encoding="utf-8")
            (root / "evidence.txt").write_text("tests pass", encoding="utf-8")

            promoted = promote_capability(root, "memory-auditor", evidence=["evidence.txt"])

        self.assertEqual("PASS", promoted["verdict"])
        self.assertEqual("active", promoted["status"])


if __name__ == "__main__":
    unittest.main()
