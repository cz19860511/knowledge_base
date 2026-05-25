from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .evolution_confirmation import list_evolution_confirmations, record_evolution_confirmation, write_evolution_confirmation_report


class EvolutionConfirmationTests(unittest.TestCase):
    def test_record_and_list_confirmations(self) -> None:
        root = Path(tempfile.mkdtemp())
        suggestion = {
            "suggestion_id": "evs_1",
            "category": "pipeline_stability",
            "title": "参数优化建议模板",
            "summary": "test",
            "recommendation": "test",
            "evidence": ["a"],
            "scope": "pipeline",
            "risk_level": "medium",
            "priority": 2,
            "requires_human_confirmation": True,
            "related_event_types": ["chunk"],
            "related_knowledge_base_ids": ["kb1"],
        }

        record = record_evolution_confirmation(
            root,
            decision="approve",
            decided_by="tester",
            note="ok",
            suggestion=suggestion,
        )
        payload = list_evolution_confirmations(root)

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["decision"], "approve")
        self.assertEqual(record["suggestion"]["title"], "参数优化建议模板")

    def test_write_evolution_confirmation_report(self) -> None:
        root = Path(tempfile.mkdtemp())
        suggestion = {
            "suggestion_id": "evs_1",
            "category": "pipeline_stability",
            "title": "参数优化建议模板",
            "summary": "test",
            "recommendation": "test",
        }
        record_evolution_confirmation(root, decision="defer", decided_by="tester", suggestion=suggestion)
        output = write_evolution_confirmation_report(root)
        self.assertTrue(output.exists())
        self.assertIn("自进化建议人工确认记录", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
