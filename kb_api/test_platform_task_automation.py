from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .evolution_confirmation import record_evolution_confirmation
from .platform_tasks import create_platform_task_from_confirmation
from .platform_task_scheduler import load_platform_task_report_automation_status, run_platform_task_report_automation


class PlatformTaskAutomationTests(unittest.TestCase):
    def test_manual_task_report_automation_creates_due_and_weekly_reports(self) -> None:
        root = Path(tempfile.mkdtemp())
        confirmation = record_evolution_confirmation(
            root,
            decision="approve",
            decided_by="tester",
            suggestion={
                "suggestion_id": "evs_auto_1",
                "category": "platform_task",
                "title": "任务自动汇总测试",
                "summary": "test",
                "recommendation": "keep going",
                "priority": 2,
            },
        )
        create_platform_task_from_confirmation(
            root,
            confirmation=confirmation,
            owner="alice",
            due_date="2026-05-24",
            event_date="2026-05-24",
        )

        payload = run_platform_task_report_automation(root, report_date="2026-05-24", force=True)

        self.assertEqual(payload["last_success_date"], "2026-05-24")
        self.assertEqual(len(payload["results"]), 1)
        self.assertTrue((root / "operations" / "platform_task_due" / "2026-05-24.md").exists())
        self.assertTrue((root / "operations" / "platform_tasks_weekly" / "2026-05-24.md").exists())

        status = load_platform_task_report_automation_status(root)
        self.assertEqual(status["last_success_date"], "2026-05-24")
        self.assertEqual(status["pending_dates"], [])


if __name__ == "__main__":
    unittest.main()
