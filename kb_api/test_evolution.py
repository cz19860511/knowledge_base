from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .evolution import build_evolution_suggestions, get_evolution_templates, write_evolution_report
from .operation_log import append_operation_event


class EvolutionSuggestionTests(unittest.TestCase):
    def test_build_evolution_suggestions_from_events(self) -> None:
        root = Path(tempfile.mkdtemp())
        append_operation_event(root, event_type="upload", knowledge_base_id="kb1", params={"folder": "a"})
        append_operation_event(root, event_type="chunk", knowledge_base_id="kb1", status="failed", error_message="boom")
        append_operation_event(root, event_type="knowledge_base_activate", knowledge_base_id="kb2", params={"knowledge_base_id": "kb2"})

        payload = build_evolution_suggestions(root, event_date=None)

        self.assertEqual(payload["total_events"], 3)
        self.assertGreaterEqual(payload["total_suggestions"], 1)
        self.assertTrue(payload["summary"])
        self.assertTrue(payload["suggestions"])
        self.assertTrue(any(item["category"] == "pipeline_stability" for item in payload["suggestions"]))

    def test_write_evolution_report(self) -> None:
        root = Path(tempfile.mkdtemp())
        append_operation_event(root, event_type="upload", knowledge_base_id="kb1", params={"folder": "a"})
        output = write_evolution_report(root, event_date=None)
        self.assertTrue(output.exists())
        content = output.read_text(encoding="utf-8")
        self.assertIn("知识平台自进化建议", content)

    def test_get_evolution_templates(self) -> None:
        payload = get_evolution_templates()
        self.assertEqual(payload["template_pack_id"], "evolution_suggestion_templates_v1")
        self.assertEqual(len(payload["templates"]), 3)
        self.assertEqual(
            [item["template_id"] for item in payload["templates"]],
            ["optimize_parameters", "rollback_action", "supplement_data"],
        )


if __name__ == "__main__":
    unittest.main()
