from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .asset_manifest import list_asset_versions, record_asset_version


class AssetManifestTests(unittest.TestCase):
    def test_record_and_list_versions(self) -> None:
        root = Path(tempfile.mkdtemp())
        first = record_asset_version(
            root,
            knowledge_base_id="kb1",
            asset_type="raw_file",
            stage="raw",
            logical_path="folder/a.txt",
            file_path="/tmp/a.txt",
            checksum="sum1",
            size_bytes=12,
            created_by="webui",
        )
        second = record_asset_version(
            root,
            knowledge_base_id="kb1",
            asset_type="raw_file",
            stage="raw",
            logical_path="folder/a.txt",
            file_path="/tmp/a.txt",
            checksum="sum2",
            size_bytes=24,
            created_by="webui",
        )

        payload = list_asset_versions(root, knowledge_base_id="kb1", asset_type="raw_file", stage="raw")

        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["items"][0]["asset_id"], first["asset_id"])
        self.assertEqual(payload["items"][1]["asset_id"], second["asset_id"])
        self.assertEqual(payload["items"][1]["parent_asset_id"], first["asset_id"])


if __name__ == "__main__":
    unittest.main()
