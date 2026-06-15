import tempfile
import unittest
from pathlib import Path

from harness_core.codex_preflight import build_codex_preflight, render_codex_preflight_context_pack
from harness_core.memory_index import record_memory


class CodexPreflightTests(unittest.TestCase):
    def test_builds_compact_memory_rag_payload_before_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text("def login():\n    return 'token'\n" * 200, encoding="utf-8")
            (root / "billing.py").write_text("def invoice():\n    return 'paid'\n" * 200, encoding="utf-8")
            memory = root / "memory.jsonl"
            record_memory(memory, content="Auth login token decision", source="handoff.md", kind="decision")

            report = build_codex_preflight(root, "fix login token bug", memory_path=memory, max_codex_chars=4000)

        self.assertEqual("PASS", report["verdict"])
        self.assertTrue(report["must_use_before_codex"])
        self.assertIn("memory_pack", report["stages"])
        self.assertIn("hybrid_rag", report["stages"])
        self.assertLess(report["codex_payload_tokens_estimate"], report["raw_tokens_estimate"])
        self.assertLessEqual(len(report["codex_payload"]), 4000)

    def test_uses_local_distiller_when_supplied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text("def login():\n    return 'token'\n" * 200, encoding="utf-8")

            report = build_codex_preflight(
                root,
                "summarize auth",
                memory_path=root / "missing.jsonl",
                max_codex_chars=4000,
                local_distiller=lambda context, task: {
                    "context": "distilled auth context",
                    "usage": {"prompt_eval_count": 100, "eval_count": 20},
                },
            )

        self.assertIn("local_qwen_distill", report["stages"])
        self.assertEqual("distilled auth context", report["codex_payload"])
        self.assertEqual(120, report["local_usage"]["total_tokens"])

    def test_rejects_local_distill_that_invents_operational_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text("def login():\n    return 'token'\n" * 200, encoding="utf-8")

            report = build_codex_preflight(
                root,
                "summarize auth",
                memory_path=root / "missing.jsonl",
                max_codex_chars=4000,
                local_distiller=lambda context, task: {
                    "context": "Fix routing for Codex ready, Claude unavailable, and Antigravity degraded.\nUse auth.py.",
                    "usage": {"prompt_eval_count": 100, "eval_count": 20},
                },
            )

        self.assertIn("local_qwen_distill_rejected", report["stages"])
        self.assertIn("unsafe_operational_status", report["local_distill_warning"])
        self.assertNotIn("Unavailable", report["codex_payload"])

    def test_renders_auditable_context_pack_with_payload_fenced(self):
        report = {
            "task": "fix login token bug",
            "stages": ["memory_pack", "hybrid_rag", "local_qwen_distill"],
            "raw_tokens_estimate": 1000,
            "codex_payload_tokens_estimate": 100,
            "estimated_codex_input_reduction_percent": 90.0,
            "codex_payload": "distilled auth context",
        }

        rendered = render_codex_preflight_context_pack(
            report,
            root=Path("/tmp/repo"),
            context_pack_path=Path("/tmp/repo/production_artifacts/context_packs/codex-preflight-context.md"),
        )

        self.assertIn("# Codex Preflight Context Pack", rendered)
        self.assertIn("path: production_artifacts/context_packs/codex-preflight-context.md", rendered)
        self.assertIn("source: memory_pack, hybrid_rag, local_qwen_distill", rendered)
        self.assertIn("```text\ndistilled auth context\n```", rendered)


if __name__ == "__main__":
    unittest.main()
