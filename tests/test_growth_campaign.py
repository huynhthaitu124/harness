from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from harness_core.growth_campaign import campaign_status, init_campaign


class GrowthCampaignTests(unittest.TestCase):
    def test_campaign_is_not_complete_before_target_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "campaign.json"
            started = datetime(2026, 6, 15, tzinfo=timezone.utc)
            init_campaign(path, target_hours=10, started_at=started)

            status = campaign_status(path, now=started + timedelta(hours=2), cycle_dir=Path(tmp) / "cycles")

        self.assertEqual("IN_PROGRESS", status["verdict"])
        self.assertEqual(8.0, status["remaining_hours"])

    def test_campaign_requires_cycles_and_source_coverage_after_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "campaign.json"
            started = datetime(2026, 6, 15, tzinfo=timezone.utc)
            init_campaign(path, target_hours=10, started_at=started, required_categories=["codex", "anthropic", "ollama", "mcp"])

            status = campaign_status(path, now=started + timedelta(hours=11), cycle_dir=root / "cycles")

        self.assertEqual("NEEDS_WORK", status["verdict"])
        self.assertIn("no_growth_cycles", status["missing"])
        self.assertIn("missing_category:codex", status["missing"])

    def test_campaign_passes_with_duration_cycles_and_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cycles = root / "cycles"
            cycles.mkdir()
            path = root / "campaign.json"
            started = datetime(2026, 6, 15, tzinfo=timezone.utc)
            init_campaign(path, target_hours=10, started_at=started, required_categories=["codex", "anthropic"])
            (cycles / "one.json").write_text(
                '{"topic":"docs","sources":[{"url":"https://developers.openai.com/codex"},{"url":"https://platform.claude.com/docs"}],"action_count":1}',
                encoding="utf-8",
            )

            status = campaign_status(path, now=started + timedelta(hours=10), cycle_dir=cycles)

        self.assertEqual("PASS", status["verdict"])


if __name__ == "__main__":
    unittest.main()
