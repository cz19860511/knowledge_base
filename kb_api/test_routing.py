from __future__ import annotations

import tempfile
import unittest

from knowledge_base_paths import resolve_knowledge_base_id_for_request
from knowledge_base_registry import save_registry


class KnowledgeBaseRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root_dir = self.tmp.name
        save_registry(
            self.root_dir,
            {
                "version": 1,
                "active_knowledge_base_id": "ai_qna_standard_v1",
                "items": [
                    {
                        "knowledge_base_id": "ai_qna_standard_v1",
                        "name": "AI+智能问答智能体标准库",
                        "status": "active",
                        "root_dir": f"{self.root_dir}/kb1",
                        "default_batch_id": "batch_20260521",
                    },
                    {
                        "knowledge_base_id": "ai_qna_standard_v2",
                        "name": "AI+智能问答智能体标准库V2",
                        "status": "paused",
                        "root_dir": f"{self.root_dir}/kb2",
                        "default_batch_id": "batch_20260522",
                    },
                ],
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_explicit_knowledge_base_id_has_priority(self) -> None:
        kb_id = resolve_knowledge_base_id_for_request(
            self.root_dir,
            knowledge_base_id="ai_qna_standard_v2",
            knowledge_base_ids=["ai_qna_standard_v1", "ai_qna_standard_v2"],
        )
        self.assertEqual(kb_id, "ai_qna_standard_v2")

    def test_knowledge_base_ids_fallbacks_to_allowed_candidate(self) -> None:
        kb_id = resolve_knowledge_base_id_for_request(
            self.root_dir,
            knowledge_base_ids=["ai_qna_standard_v2"],
        )
        self.assertEqual(kb_id, "ai_qna_standard_v2")

    def test_empty_request_uses_active_knowledge_base(self) -> None:
        kb_id = resolve_knowledge_base_id_for_request(self.root_dir)
        self.assertEqual(kb_id, "ai_qna_standard_v1")

    def test_conflicting_request_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_knowledge_base_id_for_request(
                self.root_dir,
                knowledge_base_id="ai_qna_standard_v1",
                knowledge_base_ids=["ai_qna_standard_v2"],
            )

    def test_unknown_explicit_knowledge_base_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_knowledge_base_id_for_request(
                self.root_dir,
                knowledge_base_id="missing_kb",
            )


if __name__ == "__main__":
    unittest.main()
