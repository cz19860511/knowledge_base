from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .daily_report_scheduler import load_daily_report_automation_status, run_daily_report_automation
from .operation_log import append_operation_event


class DailyReportAutomationTests(unittest.TestCase):
    def test_manual_daily_report_ingest_creates_report_and_memory_assets(self) -> None:
        root = Path(tempfile.mkdtemp())
        append_operation_event(root, event_type="upload", knowledge_base_id="kb1", params={"folder": "a"})
        append_operation_event(root, event_type="chunk", knowledge_base_id="kb1", status="failed", error_message="boom")

        result = run_daily_report_automation(root, report_date="2026-05-23", force=True)

        self.assertEqual(result["last_success_date"], "2026-05-23")
        self.assertEqual(len(result["results"]), 1)

        report_path = root / "operations" / "daily" / "2026-05-23.md"
        memory_root = root / "knowledge_bases" / "platform_run_memory"
        chunks_path = memory_root / "chunks" / "batch_20260521" / "chunks.jsonl"
        vector_path = memory_root / "vectors" / "batch_20260521" / "vector_manifest.json"

        self.assertTrue(report_path.exists())
        self.assertTrue(chunks_path.exists())
        self.assertTrue(vector_path.exists())

        status = load_daily_report_automation_status(root)
        self.assertEqual(status["last_success_date"], "2026-05-23")
        self.assertEqual(status["pending_dates"], [])


if __name__ == "__main__":
    unittest.main()
