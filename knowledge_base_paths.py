from __future__ import annotations

from pathlib import Path


def get_knowledge_base_root(root_dir: Path | str | None = None, knowledge_base_id: str | None = None) -> Path:
    from kb_api.config import settings
    from knowledge_base_registry import get_active_registry_item, load_registry

    base_dir = Path(root_dir or settings.root_dir)
    registry = load_registry(base_dir)
    if knowledge_base_id:
        for item in registry.get("items", []):
            if item.get("knowledge_base_id") == knowledge_base_id:
                candidate = str(item.get("root_dir") or "").strip()
                if candidate:
                    return Path(candidate)
        return base_dir

    active_item = get_active_registry_item(base_dir)
    candidate = str(active_item.get("root_dir") or "").strip()
    if candidate:
        return Path(candidate)
    return base_dir


def get_active_knowledge_base_id(root_dir: Path | str | None = None) -> str:
    from kb_api.config import settings
    from knowledge_base_registry import get_active_registry_item

    base_dir = Path(root_dir or settings.root_dir)
    item = get_active_registry_item(base_dir)
    return str(item.get("knowledge_base_id") or settings.knowledge_base_id)


def get_knowledge_base_workspace_paths(
    root_dir: Path | str | None = None,
    knowledge_base_id: str | None = None,
) -> dict[str, Path]:
    from kb_api.config import settings
    from knowledge_base_registry import get_active_registry_item, load_registry

    base_dir = Path(root_dir or settings.root_dir)
    registry = load_registry(base_dir)
    if knowledge_base_id:
        item = next((row for row in registry.get("items", []) if row.get("knowledge_base_id") == knowledge_base_id), {})
    else:
        item = get_active_registry_item(base_dir)

    kb_root = get_knowledge_base_root(base_dir, knowledge_base_id)
    batch_id = str(item.get("default_batch_id") or settings.batch_id).strip() or settings.batch_id

    return {
        "root_dir": kb_root,
        "raw_source_root": kb_root / "raw" / "标准化体系_分类版",
        "raw_versions_root": kb_root / "raw_versions",
        "operations_dir": kb_root / "operations",
        "selected_dir": kb_root / "selected",
        "rag_dir": kb_root / "rag",
        "models_dir": kb_root / "models",
        "chunks_dir": kb_root / "chunks" / batch_id,
        "vectors_dir": kb_root / "vectors" / batch_id,
    }


def ensure_knowledge_base_workspace(
    root_dir: Path | str | None = None,
    knowledge_base_id: str | None = None,
) -> dict[str, Path]:
    paths = get_knowledge_base_workspace_paths(root_dir=root_dir, knowledge_base_id=knowledge_base_id)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
