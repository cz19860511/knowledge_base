from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .asset_manifest import record_asset_version
from .operation_log import append_operation_event
from .replay import build_replay_report, write_replay_report


class ReplayReportTests(unittest.TestCase):
    def test_build_replay_report(self) -> None:
        root = Path(tempfile.mkdtemp())
        append_operation_event(
            root,
            event_type="upload",
            knowledge_base_id="kb1",
            output_assets=[{"stage": "raw", "kb_id": "kb1", "file_path": "/tmp/a.txt"}],
        )
        record_asset_version(
            root,
            knowledge_base_id="kb1",
            asset_type="raw_file",
            stage="raw",
            logical_path="folder/a.txt",
            file_path="/tmp/a.txt",
            created_by="webui",
        )

        payload = build_replay_report(root)

        self.assertEqual(payload["event_total"], 1)
        self.assertTrue(payload["summary"])
        self.assertTrue(payload["daily_report"]["content"])

    def test_write_replay_report(self) -> None:
        root = Path(tempfile.mkdtemp())
        append_operation_event(root, event_type="upload", knowledge_base_id="kb1")
        output = write_replay_report(root)
        self.assertTrue(output.exists())
        self.assertIn("平台事件回放", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
