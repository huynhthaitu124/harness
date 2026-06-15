from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from harness_core.memory_index import build_memory_pack, record_memory, search_memories, sync_artifact_memories


class MemoryIndexTests(unittest.TestCase):
    def test_deduplicates_identical_memory_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.jsonl"
            first = record_memory(path, content="Claude quota resets at 1:50am", source="handoff.md", kind="operational")
            second = record_memory(path, content="Claude quota resets at 1:50am", source="other.md", kind="operational")

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])

    def test_search_balances_relevance_importance_and_recency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.jsonl"
            now = datetime(2026, 6, 15, tzinfo=timezone.utc)
            record_memory(path, content="auth token login architecture", source="a", kind="decision", importance=0.9, timestamp=now)
            record_memory(path, content="billing invoice payment", source="b", kind="note", importance=1.0, timestamp=now)
            record_memory(path, content="auth token old note", source="c", kind="note", importance=0.2, timestamp=now - timedelta(days=300))

            results = search_memories(path, "auth token", top_k=2, now=now)

        self.assertEqual("a", results[0]["source"])
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_memory_pack_is_bounded_and_cites_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.jsonl"
            for index in range(20):
                record_memory(path, content=f"routing token memory {index} " * 20, source=f"source-{index}.md", kind="note")

            pack = build_memory_pack(path, "routing token", top_k=10, max_chars=800)

        self.assertLessEqual(len(pack), 800)
        self.assertIn("source:", pack)

    def test_syncs_growth_cycles_and_structured_handoffs_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cycles = root / "production_artifacts" / "self_growth"
            handoffs = root / "production_artifacts" / "handoffs"
            cycles.mkdir(parents=True)
            handoffs.mkdir(parents=True)
            (cycles / "cycle.json").write_text(
                '{"topic":"adaptive routing","sources":[],"actions":["Added quota feedback"],"action_count":1}',
                encoding="utf-8",
            )
            (handoffs / "handoff.json").write_text(
                '{"title":"Review","summary":"Ready for review","from_center":"codex","to_center":"claude","task_fingerprint":"task-v1","evidence":["tests.txt"]}',
                encoding="utf-8",
            )
            memory = root / "production_artifacts" / "memory.jsonl"

            first = sync_artifact_memories(root, memory)
            second = sync_artifact_memories(root, memory)

        self.assertEqual(2, first["created_count"])
        self.assertEqual(0, second["created_count"])
        self.assertEqual(2, second["duplicate_count"])


if __name__ == "__main__":
    unittest.main()
