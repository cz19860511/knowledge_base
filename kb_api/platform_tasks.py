from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_date() -> str:
    return datetime.now().date().isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def get_task_ledger_path(root_dir: Path | str, event_date: str | None = None) -> Path:
    day = event_date or _default_date()
    return Path(root_dir) / "operations" / "platform_tasks" / f"{day}.jsonl"


def get_task_history_path(root_dir: Path | str, event_date: str | None = None) -> Path:
    day = event_date or _default_date()
    return Path(root_dir) / "operations" / "platform_tasks_history" / f"{day}.jsonl"


def _append_task_history(root_dir: Path | str, payload: dict, *, event_date: str | None = None) -> None:
    _append_jsonl(get_task_history_path(root_dir, event_date=event_date), payload)


def _load_tasks(root_dir: Path | str, event_date: str | None = None) -> list[dict]:
    return _read_jsonl(get_task_ledger_path(root_dir, event_date=event_date))


def _allowed_status_transitions(current: str) -> set[str]:
    table = {
        "pending": {"ready", "running", "blocked", "cancelled"},
        "ready": {"running", "blocked", "cancelled"},
        "running": {"blocked", "done", "cancelled"},
        "blocked": {"ready", "running", "cancelled"},
        "done": {"running", "cancelled"},
        "cancelled": set(),
    }
    return table.get(current, {"pending", "ready", "running", "blocked", "done", "cancelled"})


def _latest_task(items: list[dict], task_id: str) -> dict | None:
    for item in reversed(items):
        if str(item.get("task_id") or "") == task_id:
            return item
    return None


def create_platform_task(
    root_dir: Path | str,
    *,
    title: str,
    summary: str,
    priority: int = 3,
    status: str = "pending",
    owner: str = "",
    due_date: str = "",
    source_type: str = "manual",
    source_id: str = "",
    source_report_date: str = "",
    source_report_path: str = "",
    source_payload: dict | None = None,
    created_by: str = "system",
    note: str = "",
    event_date: str | None = None,
) -> dict:
    payload = {
        "task_id": f"ptk_{uuid4().hex}",
        "title": title,
        "summary": summary,
        "priority": priority,
        "status": status,
        "owner": owner,
        "due_date": due_date,
        "source_type": source_type,
        "source_id": source_id,
        "source_report_date": source_report_date,
        "source_report_path": source_report_path,
        "source_payload": source_payload or {},
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "note": note,
    }
    _append_jsonl(get_task_ledger_path(root_dir, event_date=event_date), payload)
    _append_task_history(
        root_dir,
        {
            "event_id": f"pte_{uuid4().hex}",
            "task_id": payload["task_id"],
            "event_type": "created",
            "status": payload["status"],
            "created_at": _now_iso(),
            "source_type": payload["source_type"],
            "source_id": payload["source_id"],
            "note": payload["note"],
        },
        event_date=event_date,
    )
    return payload


def create_platform_task_from_confirmation(
    root_dir: Path | str,
    *,
    confirmation: dict,
    owner: str = "",
    due_date: str = "",
    status: str = "pending",
    created_by: str = "system",
    note: str = "",
    event_date: str | None = None,
) -> dict:
    suggestion = confirmation.get("suggestion", {}) if isinstance(confirmation, dict) else {}
    title = str(suggestion.get("title") or "未命名任务")
    summary = str(suggestion.get("recommendation") or suggestion.get("summary") or "")
    return create_platform_task(
        root_dir,
        title=title,
        summary=summary,
        priority=int(suggestion.get("priority", 3) or 3),
        status=status,
        owner=owner,
        due_date=due_date,
        source_type="confirmation",
        source_id=str(confirmation.get("confirmation_id") or ""),
        source_report_date=str(confirmation.get("source_report_date") or ""),
        source_report_path=str(confirmation.get("source_report_path") or ""),
        source_payload=confirmation,
        created_by=created_by,
        note=note or str(confirmation.get("note") or ""),
        event_date=event_date,
    )


def list_platform_tasks(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    limit: int = 500,
) -> dict:
    path = get_task_ledger_path(root_dir, event_date=event_date)
    items = _read_jsonl(path)
    if status:
        items = [item for item in items if str(item.get("status") or "").strip() == status]
    if source_type:
        items = [item for item in items if str(item.get("source_type") or "").strip() == source_type]
    items = items[-limit:] if limit > 0 else items
    return {
        "total": len(items),
        "event_date": event_date or _default_date(),
        "task_path": str(path),
        "items": items,
    }


def update_platform_task(
    root_dir: Path | str,
    *,
    task_id: str,
    status: str | None = None,
    owner: str | None = None,
    due_date: str | None = None,
    note: str | None = None,
    event_date: str | None = None,
) -> dict:
    path = get_task_ledger_path(root_dir, event_date=event_date)
    items = _read_jsonl(path)
    updated: dict | None = None
    for item in reversed(items):
        if str(item.get("task_id") or "") == task_id:
            if status is not None:
                item["status"] = status
            if owner is not None:
                item["owner"] = owner
            if due_date is not None:
                item["due_date"] = due_date
            if note is not None:
                item["note"] = note
            item["updated_at"] = _now_iso()
            updated = item
            break
    if updated is None:
        raise FileNotFoundError(f"task not found: {task_id}")
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")
    _append_task_history(
        root_dir,
        {
            "event_id": f"pte_{uuid4().hex}",
            "task_id": task_id,
            "event_type": "updated",
            "status": updated.get("status", ""),
            "created_at": _now_iso(),
            "note": note or "",
            "owner": updated.get("owner", ""),
            "due_date": updated.get("due_date", ""),
        },
        event_date=event_date,
    )
    return updated


def get_platform_task(
    root_dir: Path | str,
    *,
    task_id: str,
    event_date: str | None = None,
) -> dict:
    items = _load_tasks(root_dir, event_date=event_date)
    task = _latest_task(items, task_id)
    if task is None:
        raise FileNotFoundError(f"task not found: {task_id}")
    history = _read_jsonl(get_task_history_path(root_dir, event_date=event_date))
    task_history = [item for item in history if str(item.get("task_id") or "") == task_id]
    return {
        "task": task,
        "history": task_history,
        "history_path": str(get_task_history_path(root_dir, event_date=event_date)),
    }


def transition_platform_task(
    root_dir: Path | str,
    *,
    task_id: str,
    target_status: str,
    owner: str | None = None,
    due_date: str | None = None,
    note: str | None = None,
    event_date: str | None = None,
) -> dict:
    items = _load_tasks(root_dir, event_date=event_date)
    task = _latest_task(items, task_id)
    if task is None:
        raise FileNotFoundError(f"task not found: {task_id}")
    current = str(task.get("status") or "").strip() or "pending"
    if target_status not in _allowed_status_transitions(current):
        raise ValueError(f"invalid transition: {current} -> {target_status}")
    task["status"] = target_status
    if owner is not None:
        task["owner"] = owner
    if due_date is not None:
        task["due_date"] = due_date
    if note is not None:
        task["note"] = note
    task["updated_at"] = _now_iso()
    path = get_task_ledger_path(root_dir, event_date=event_date)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")
    _append_task_history(
        root_dir,
        {
            "event_id": f"pte_{uuid4().hex}",
            "task_id": task_id,
            "event_type": "transitioned",
            "from_status": current,
            "to_status": target_status,
            "created_at": _now_iso(),
            "owner": task.get("owner", ""),
            "due_date": task.get("due_date", ""),
            "note": note or "",
        },
        event_date=event_date,
    )
    return task


def build_task_report(root_dir: Path | str, *, event_date: str | None = None) -> dict:
    payload = list_platform_tasks(root_dir, event_date=event_date)
    counts: dict[str, int] = {}
    for item in payload["items"]:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "report_date": payload["event_date"],
        "generated_at": _now_iso(),
        "total": payload["total"],
        "counts": counts,
        "task_path": payload["task_path"],
        "items": payload["items"],
    }


def write_task_report(root_dir: Path | str, *, event_date: str | None = None, output_path: Path | None = None) -> Path:
    payload = build_task_report(root_dir, event_date=event_date)
    day = payload["report_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "platform_tasks" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# 平台任务台账 {day}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 任务总数：{payload['total']}",
        "",
        "## 状态统计",
        "",
    ]
    if payload["counts"]:
        for status, count in payload["counts"].items():
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 任务清单", ""])
    if payload["items"]:
        for item in payload["items"][-80:]:
            lines.append(
                f"- [{item.get('status', '')}] `{item.get('title', '')}` "
                f"priority=`{item.get('priority', '')}` owner=`{item.get('owner', '') or '-'}` "
                f"due=`{item.get('due_date', '') or '-'}`"
            )
    else:
        lines.append("- 无")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_task_history_report(root_dir: Path | str, *, event_date: str | None = None) -> dict:
    path = get_task_history_path(root_dir, event_date=event_date)
    items = _read_jsonl(path)
    counts: dict[str, int] = {}
    transitions: dict[str, int] = {}
    for item in items:
        event_type = str(item.get("event_type") or "unknown")
        counts[event_type] = counts.get(event_type, 0) + 1
        if event_type == "transitioned":
            key = f"{item.get('from_status', '')}->{item.get('to_status', '')}"
            transitions[key] = transitions.get(key, 0) + 1
    return {
        "report_date": event_date or _default_date(),
        "generated_at": _now_iso(),
        "total": len(items),
        "history_path": str(path),
        "items": items,
        "event_counts": counts,
        "transition_counts": transitions,
    }


def write_task_history_report(root_dir: Path | str, *, event_date: str | None = None, output_path: Path | None = None) -> Path:
    payload = build_task_history_report(root_dir, event_date=event_date)
    day = payload["report_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "platform_tasks_history" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# 平台任务历史轨迹 {day}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 历史总数：{payload['total']}",
        f"- 历史路径：{payload['history_path']}",
        "",
        "## 事件统计",
        "",
    ]
    if payload["event_counts"]:
        for event_type, count in payload["event_counts"].items():
            lines.append(f"- {event_type}: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 状态流转统计", ""])
    if payload["transition_counts"]:
        for key, count in payload["transition_counts"].items():
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 历史明细", ""])
    if payload["items"]:
        for item in payload["items"][-120:]:
            lines.append(
                f"- [{item.get('created_at', '')}] `{item.get('event_type', '')}` "
                f"task=`{item.get('task_id', '')}` status=`{item.get('status', '')}` "
                f"from=`{item.get('from_status', '') or '-'}` to=`{item.get('to_status', '') or '-'}`"
            )
    else:
        lines.append("- 无")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
