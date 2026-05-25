from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .evolution_confirmation import record_evolution_confirmation
from .platform_tasks import build_task_history_report, build_task_report, create_platform_task_from_confirmation, get_platform_task, list_platform_tasks, transition_platform_task, write_task_history_report, write_task_report


class PlatformTaskTests(unittest.TestCase):
    def test_create_task_from_confirmation(self) -> None:
        root = Path(tempfile.mkdtemp())
        confirmation = record_evolution_confirmation(
            root,
            decision="approve",
            decided_by="tester",
            suggestion={
                "suggestion_id": "evs_1",
                "category": "pipeline_stability",
                "title": "参数优化建议模板",
                "summary": "test",
                "recommendation": "reduce chunk size",
                "priority": 2,
            },
        )

        task = create_platform_task_from_confirmation(root, confirmation=confirmation, owner="alice", due_date="2026-05-30")
        payload = list_platform_tasks(root)

        self.assertEqual(payload["total"], 1)
        self.assertEqual(task["title"], "参数优化建议模板")
        self.assertEqual(task["source_type"], "confirmation")
        self.assertEqual(task["owner"], "alice")

    def test_write_task_report(self) -> None:
        root = Path(tempfile.mkdtemp())
        write_task_report(root)
        report = build_task_report(root)
        self.assertTrue(report["task_path"])
        self.assertEqual(report["total"], 0)

    def test_write_task_history_report(self) -> None:
        root = Path(tempfile.mkdtemp())
        confirmation = record_evolution_confirmation(
            root,
            decision="approve",
            decided_by="tester",
            suggestion={
                "suggestion_id": "evs_3",
                "category": "pipeline_stability",
                "title": "历史报告测试",
                "summary": "test",
                "recommendation": "adjust",
                "priority": 2,
            },
        )
        task = create_platform_task_from_confirmation(root, confirmation=confirmation, owner="alice", due_date="2026-05-30")
        transition_platform_task(root, task_id=task["task_id"], target_status="ready", note="准备执行")
        write_task_history_report(root)
        report = build_task_history_report(root)
        self.assertTrue(report["history_path"])
        self.assertGreaterEqual(report["total"], 2)

    def test_get_and_transition_task(self) -> None:
        root = Path(tempfile.mkdtemp())
        confirmation = record_evolution_confirmation(
            root,
            decision="approve",
            decided_by="tester",
            suggestion={
                "suggestion_id": "evs_2",
                "category": "pipeline_stability",
                "title": "任务流转测试",
                "summary": "test",
                "recommendation": "adjust",
                "priority": 2,
            },
        )
        task = create_platform_task_from_confirmation(root, confirmation=confirmation, owner="alice", due_date="2026-05-30")
        detail = get_platform_task(root, task_id=task["task_id"])
        self.assertEqual(detail["task"]["task_id"], task["task_id"])
        updated = transition_platform_task(root, task_id=task["task_id"], target_status="ready", note="准备执行")
        self.assertEqual(updated["status"], "ready")
        self.assertEqual(len(get_platform_task(root, task_id=task["task_id"])["history"]), 2)


if __name__ == "__main__":
    unittest.main()
