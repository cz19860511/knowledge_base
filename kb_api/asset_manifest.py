from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .config import settings


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_manifest() -> dict:
    return {"version": 1, "assets": []}


def get_asset_manifest_path(root_dir: Path | str | None = None) -> Path:
    base = Path(root_dir or settings.root_dir)
    return base / "operations" / "asset_manifest.json"


def _load_manifest(root_dir: Path | str | None = None) -> dict:
    return _read_json(get_asset_manifest_path(root_dir), _default_manifest())


def _save_manifest(root_dir: Path | str | None, payload: dict) -> None:
    _write_json(get_asset_manifest_path(root_dir), payload)


def _key(asset: dict) -> tuple[str, str, str, str]:
    return (
        str(asset.get("knowledge_base_id") or "").strip(),
        str(asset.get("asset_type") or "").strip(),
        str(asset.get("stage") or "").strip(),
        str(asset.get("logical_path") or "").strip(),
    )


def _count_versions(assets: list[dict], key: tuple[str, str, str, str]) -> int:
    return sum(1 for asset in assets if _key(asset) == key)


def _last_asset(assets: list[dict], key: tuple[str, str, str, str]) -> dict | None:
    for asset in reversed(assets):
        if _key(asset) == key:
            return asset
    return None


def record_asset_version(
    root_dir: Path | str | None,
    *,
    knowledge_base_id: str,
    asset_type: str,
    stage: str,
    logical_path: str,
    file_path: str = "",
    checksum: str = "",
    size_bytes: int = 0,
    created_by: str = "system",
    status: str = "active",
    operation_id: str = "",
    parent_asset_id: str = "",
    source_asset_ids: list[str] | None = None,
    metadata: dict | None = None,
    version: str | None = None,
) -> dict:
    manifest = _load_manifest(root_dir)
    assets = manifest.setdefault("assets", [])
    key = (knowledge_base_id, asset_type, stage, logical_path)
    parent = _last_asset(assets, key)
    record = {
        "asset_id": f"asset_{uuid4().hex}",
        "knowledge_base_id": knowledge_base_id,
        "asset_type": asset_type,
        "stage": stage,
        "logical_path": logical_path,
        "version": version or f"v{_count_versions(assets, key) + 1}",
        "status": status,
        "file_path": file_path,
        "checksum": checksum,
        "size_bytes": int(size_bytes or 0),
        "created_by": created_by,
        "created_at": _now_iso(),
        "operation_id": operation_id or "",
        "parent_asset_id": parent_asset_id or (str(parent.get("asset_id") or "") if parent else ""),
        "source_asset_ids": source_asset_ids or [],
        "metadata": metadata or {},
    }
    assets.append(record)
    _save_manifest(root_dir, manifest)
    return record


def list_asset_versions(
    root_dir: Path | str | None,
    *,
    knowledge_base_id: str | None = None,
    asset_type: str | None = None,
    stage: str | None = None,
    logical_path: str | None = None,
    limit: int = 500,
) -> dict:
    manifest = _load_manifest(root_dir)
    assets = manifest.get("assets", [])
    items: list[dict] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if knowledge_base_id and str(asset.get("knowledge_base_id") or "").strip() != knowledge_base_id:
            continue
        if asset_type and str(asset.get("asset_type") or "").strip() != asset_type:
            continue
        if stage and str(asset.get("stage") or "").strip() != stage:
            continue
        if logical_path and str(asset.get("logical_path") or "").strip() != logical_path:
            continue
        items.append(asset)
    items = items[-limit:] if limit > 0 else items
    return {
        "total": len(items),
        "manifest_path": str(get_asset_manifest_path(root_dir)),
        "items": items,
    }
