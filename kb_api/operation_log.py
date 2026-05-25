from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _event_day(value: str | None = None) -> str:
    if value:
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            pass
    return datetime.now().date().isoformat()


def get_operation_events_path(root_dir: Path | str, knowledge_base_id: str | None = None, event_date: str | None = None) -> Path:
    base_root = Path(root_dir)
    return base_root / "operations" / "events" / f"{_event_day(event_date)}.jsonl"


def _normalize_assets(items: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for item in items or []:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def append_operation_event(
    root_dir: Path | str,
    *,
    event_type: str,
    knowledge_base_id: str | None = None,
    source: str = "api",
    actor: str = "system",
    input_assets: list[dict] | None = None,
    output_assets: list[dict] | None = None,
    params: dict | None = None,
    status: str = "success",
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_ms: int | None = None,
    error_message: str = "",
    log_path: str = "",
    remark: str = "",
) -> dict:
    event_id = f"evt_{uuid4().hex}"
    started_at = started_at or _now_iso()
    finished_at = finished_at or started_at
    payload = {
        "event_id": event_id,
        "event_type": event_type,
        "knowledge_base_id": knowledge_base_id or "",
        "source": source,
        "actor": actor,
        "input_assets": _normalize_assets(input_assets),
        "output_assets": _normalize_assets(output_assets),
        "params": params or {},
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "error_message": error_message,
        "log_path": log_path,
        "remark": remark,
        "created_at": _now_iso(),
    }
    path = get_operation_events_path(root_dir, knowledge_base_id, event_date=started_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")
    return payload


def list_operation_events(
    root_dir: Path | str,
    *,
    knowledge_base_id: str | None = None,
    event_date: str | None = None,
    limit: int = 200,
) -> dict:
    path = get_operation_events_path(root_dir, knowledge_base_id, event_date=event_date)
    if not path.exists():
        return {"total": 0, "items": [], "event_date": _event_day(event_date)}

    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if knowledge_base_id and str(item.get("knowledge_base_id") or "").strip() not in {"", knowledge_base_id}:
            continue
        items.append(item)

    items = items[-limit:] if limit > 0 else items
    return {"total": len(items), "items": items, "event_date": _event_day(event_date)}
