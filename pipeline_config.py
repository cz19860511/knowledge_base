from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any


AVAILABLE_FOLDERS = [
    "02规章制度与标准规范",
    "03SOP流程化资料_疑似",
    "04表单台账与字段说明_疑似",
    "05岗位职责与角色资料",
    "06安全与应急资料",
    "07信息系统与APP操作",
]

DEFAULT_PIPELINE_CONFIG: dict[str, Any] = {
    "version": 1,
    "preprocess": {
        "folders": AVAILABLE_FOLDERS,
        "primary_exts": [".pdf", ".docx", ".xlsx", ".pptx"],
        "supplement_exts": [".docx"],
        "markitdown_docx_enabled": True,
        "mineru_command": "mineru",
        "mineru_pipeline": "pipeline",
    },
    "chunk": {
        "folders": AVAILABLE_FOLDERS,
        "max_chunk_chars": 1800,
        "min_chunk_chars": 300,
        "mineru_parser_bonus": 50,
    },
    "embedding": {
        "provider": "transformers",
        "model_path": "/data/kb/models/bge-small-zh-v1.5",
        "model_name": "bge-small-zh-v1.5",
        "device": "cpu",
        "batch_size": 16,
        "pooling": "cls",
        "query_instruction": "为这个句子生成表示以用于检索相关文章：",
        "max_length": 512,
        "normalize": True,
    },
}


def get_pipeline_config_path(root_dir: Path | str) -> Path:
    return Path(root_dir) / "operations" / "pipeline_config.json"


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _coerce_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
    else:
        return list(default)
    return items or list(default)


def _merge_section(default_section: dict[str, Any], payload: Any) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    merged: dict[str, Any] = {}
    for key, default_value in default_section.items():
        value = raw.get(key, default_value)
        if isinstance(default_value, bool):
            merged[key] = _coerce_bool(value, default_value)
        elif isinstance(default_value, int):
            merged[key] = _coerce_int(value, default_value)
        elif isinstance(default_value, list):
            merged[key] = _coerce_list(value, list(default_value))
        else:
            merged[key] = _coerce_str(value, default_value)
    return merged


def normalize_pipeline_config(payload: Any) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    normalized: dict[str, Any] = {"version": _coerce_int(raw.get("version", 1), 1)}
    for section_name, default_section in DEFAULT_PIPELINE_CONFIG.items():
        if section_name == "version":
            continue
        normalized[section_name] = _merge_section(default_section, raw.get(section_name, {}))
    normalized["updated_at"] = _coerce_str(raw.get("updated_at", ""), "")
    return normalized


def load_pipeline_config(root_dir: Path | str) -> dict[str, Any]:
    path = get_pipeline_config_path(root_dir)
    if not path.exists():
        return deepcopy(DEFAULT_PIPELINE_CONFIG)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_PIPELINE_CONFIG)
    return normalize_pipeline_config(payload)


def save_pipeline_config(root_dir: Path | str, payload: Any) -> dict[str, Any]:
    config = normalize_pipeline_config(payload)
    config["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    path = get_pipeline_config_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def list_configurable_fields() -> dict[str, list[str]]:
    return {
        "preprocess": [
            "folders",
            "primary_exts",
            "supplement_exts",
            "markitdown_docx_enabled",
            "mineru_command",
            "mineru_pipeline",
        ],
        "chunk": [
            "folders",
            "max_chunk_chars",
            "min_chunk_chars",
            "mineru_parser_bonus",
        ],
        "embedding": [
            "provider",
            "model_path",
            "model_name",
            "device",
            "batch_size",
            "pooling",
            "query_instruction",
            "max_length",
            "normalize",
        ],
    }
