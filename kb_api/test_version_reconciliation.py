from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .asset_manifest import record_asset_version
from .operation_log import append_operation_event
from .version_reconciliation import build_version_reconciliation, write_version_reconciliation


class VersionReconciliationTests(unittest.TestCase):
    def test_build_version_reconciliation(self) -> None:
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

        payload = build_version_reconciliation(root)

        self.assertEqual(payload["event_total"], 1)
        self.assertEqual(payload["asset_total"], 1)
        self.assertEqual(payload["linked_ref_total"], 1)
        self.assertEqual(payload["missing_ref_total"], 0)
        self.assertEqual(payload["orphan_asset_total"], 0)

    def test_write_version_reconciliation(self) -> None:
        root = Path(tempfile.mkdtemp())
        append_operation_event(root, event_type="upload", knowledge_base_id="kb1")
        output = write_version_reconciliation(root)
        self.assertTrue(output.exists())
        self.assertIn("版本对账报告", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
