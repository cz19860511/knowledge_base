from __future__ import annotations

from copy import deepcopy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from kb_api.config import settings


DEFAULT_KB_ID = settings.knowledge_base_id
DEFAULT_REGISTRY: dict[str, Any] = {
    "version": 1,
    "active_knowledge_base_id": DEFAULT_KB_ID,
    "items": [
        {
            "knowledge_base_id": DEFAULT_KB_ID,
            "name": "AI+智能问答智能体标准库",
            "description": "当前默认知识库，用于 AgentArts General 联调。",
            "owner": "平台负责人",
            "status": "active",
            "root_dir": str(settings.root_dir),
            "default_batch_id": settings.batch_id,
            "doc_count": 0,
            "chunk_count": 0,
            "created_at": "",
            "updated_at": "",
        }
    ],
}


def _default_root_dir_for(kb_id: str) -> str:
    if kb_id == DEFAULT_KB_ID:
        return str(settings.root_dir)
    return str(Path(settings.root_dir) / "knowledge_bases" / kb_id)


def get_registry_path(root_dir: Path | str) -> Path:
    return Path(root_dir) / "operations" / "knowledge_bases.json"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalize_item(item: Any) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    kb_id = str(raw.get("knowledge_base_id", "")).strip()
    name = str(raw.get("name", "")).strip() or kb_id
    description = str(raw.get("description", "")).strip()
    owner = str(raw.get("owner", "")).strip()
    status = str(raw.get("status", "active")).strip() or "active"
    root_dir = str(raw.get("root_dir", _default_root_dir_for(kb_id))).strip() or _default_root_dir_for(kb_id)
    default_batch_id = str(raw.get("default_batch_id", settings.batch_id)).strip() or settings.batch_id

    return {
        "knowledge_base_id": kb_id,
        "name": name,
        "description": description,
        "owner": owner,
        "status": status,
        "root_dir": root_dir,
        "default_batch_id": default_batch_id,
        "doc_count": int(raw.get("doc_count", 0) or 0),
        "chunk_count": int(raw.get("chunk_count", 0) or 0),
        "created_at": str(raw.get("created_at", "")),
        "updated_at": str(raw.get("updated_at", "")),
    }


def normalize_registry(payload: Any) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    items = [_normalize_item(item) for item in raw.get("items", []) if isinstance(item, dict)]
    active_id = str(raw.get("active_knowledge_base_id", DEFAULT_KB_ID)).strip() or DEFAULT_KB_ID
    if not any(item["knowledge_base_id"] == active_id for item in items):
        items = deepcopy(DEFAULT_REGISTRY["items"])
        active_id = DEFAULT_KB_ID
    return {
        "version": int(raw.get("version", 1) or 1),
        "active_knowledge_base_id": active_id,
        "items": items,
        "updated_at": str(raw.get("updated_at", "")),
    }


def load_registry(root_dir: Path | str) -> dict[str, Any]:
    path = get_registry_path(root_dir)
    if not path.exists():
        registry = deepcopy(DEFAULT_REGISTRY)
        registry["updated_at"] = ""
        return registry
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        registry = deepcopy(DEFAULT_REGISTRY)
        registry["updated_at"] = ""
        return registry
    return normalize_registry(payload)


def save_registry(root_dir: Path | str, payload: Any) -> dict[str, Any]:
    registry = normalize_registry(payload)
    now = _now_iso()
    for item in registry["items"]:
        if not item.get("created_at"):
            item["created_at"] = now
        item["updated_at"] = now
    registry["updated_at"] = now
    path = get_registry_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry


def upsert_registry_item(root_dir: Path | str, item: dict[str, Any]) -> dict[str, Any]:
    registry = load_registry(root_dir)
    normalized = _normalize_item(item)
    if not normalized["knowledge_base_id"]:
        raise ValueError("knowledge_base_id is required")

    now = _now_iso()
    matched = False
    new_items: list[dict[str, Any]] = []
    for existing in registry["items"]:
        if existing["knowledge_base_id"] == normalized["knowledge_base_id"]:
            merged = {**existing, **normalized}
            merged.setdefault("created_at", existing.get("created_at") or now)
            merged["updated_at"] = now
            new_items.append(merged)
            matched = True
        else:
            new_items.append(existing)

    if not matched:
        normalized.setdefault("created_at", now)
        normalized["updated_at"] = now
        new_items.append(normalized)

    registry["items"] = new_items
    if normalized.get("status") == "active":
        registry["active_knowledge_base_id"] = normalized["knowledge_base_id"]
    registry["updated_at"] = now
    path = get_registry_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry


def delete_registry_item(root_dir: Path | str, knowledge_base_id: str) -> dict[str, Any]:
    registry = load_registry(root_dir)
    kb_id = str(knowledge_base_id).strip()
    items = [item for item in registry["items"] if item["knowledge_base_id"] != kb_id]
    if len(items) == len(registry["items"]):
        return registry
    registry["items"] = items
    if registry.get("active_knowledge_base_id") == kb_id:
        registry["active_knowledge_base_id"] = items[0]["knowledge_base_id"] if items else ""
    registry["updated_at"] = _now_iso()
    path = get_registry_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry


def set_active_registry_item(root_dir: Path | str, knowledge_base_id: str) -> dict[str, Any]:
    registry = load_registry(root_dir)
    kb_id = str(knowledge_base_id).strip()
    if not any(item["knowledge_base_id"] == kb_id for item in registry["items"]):
        raise ValueError(f"knowledge base not found: {kb_id}")
    registry["active_knowledge_base_id"] = kb_id
    registry["updated_at"] = _now_iso()
    path = get_registry_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry


def get_active_registry_item(root_dir: Path | str) -> dict[str, Any]:
    registry = load_registry(root_dir)
    active_id = registry.get("active_knowledge_base_id", DEFAULT_KB_ID)
    for item in registry.get("items", []):
        if item.get("knowledge_base_id") == active_id:
            return item
    return registry["items"][0] if registry.get("items") else _normalize_item(DEFAULT_REGISTRY["items"][0])
