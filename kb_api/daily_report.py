from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .operation_log import list_operation_events


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_date() -> str:
    return datetime.now().date().isoformat()


def _group_events_by_kb(events: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        kb_id = str(event.get("knowledge_base_id") or "platform").strip() or "platform"
        grouped[kb_id].append(event)
    return grouped


def build_daily_report(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    limit: int = 5000,
) -> dict:
    day = event_date or _default_date()
    payload = list_operation_events(root_dir, knowledge_base_id=knowledge_base_id, event_date=day, limit=limit)
    events = payload.get("items", [])
    event_types = Counter(str(item.get("event_type") or "").strip() or "unknown" for item in events)
    statuses = Counter(str(item.get("status") or "").strip() or "unknown" for item in events)
    kb_counts = Counter(str(item.get("knowledge_base_id") or "platform").strip() or "platform" for item in events)
    grouped = _group_events_by_kb(events)

    lines: list[str] = []
    title = f"# 知识平台日报 {day}"
    if knowledge_base_id:
        title += f"（知识库：{knowledge_base_id}）"
    lines.append(title)
    lines.append("")
    lines.append(f"- 生成时间：{_now_iso()}")
    lines.append(f"- 事件总数：{len(events)}")
    if knowledge_base_id:
        lines.append(f"- 过滤知识库：{knowledge_base_id}")
    lines.append("")
    lines.append("## 今日概览")
    lines.append("")
    if events:
        lines.append(f"今日共记录 {len(events)} 条操作事件，涉及 {len(kb_counts)} 个知识库/平台域。")
    else:
        lines.append("今日暂无操作事件。")
    lines.append("")
    lines.append("## 事件统计")
    lines.append("")
    lines.append("### 按事件类型")
    for event_type, count in event_types.most_common():
        lines.append(f"- {event_type}: {count}")
    if not event_types:
        lines.append("- 无")
    lines.append("")
    lines.append("### 按状态")
    for status, count in statuses.most_common():
        lines.append(f"- {status}: {count}")
    if not statuses:
        lines.append("- 无")
    lines.append("")
    lines.append("### 按知识库")
    for kb_id, count in kb_counts.most_common():
        lines.append(f"- {kb_id}: {count}")
    if not kb_counts:
        lines.append("- 无")
    lines.append("")
    lines.append("## 关键事件")
    lines.append("")
    if not events:
        lines.append("- 无")
    else:
        for event in events[-50:]:
            lines.append(
                f"- [{event.get('started_at', '')}] `{event.get('event_type', '')}` "
                f"kb=`{event.get('knowledge_base_id', '')}` status=`{event.get('status', '')}` "
                f"source=`{event.get('source', '')}` remark=`{event.get('remark', '')}`"
            )
    lines.append("")
    lines.append("## 知识库分组")
    lines.append("")
    if not grouped:
        lines.append("- 无")
    else:
        for kb_id, kb_events in grouped.items():
            lines.append(f"### {kb_id}")
            for event in kb_events[-20:]:
                lines.append(
                    f"- `{event.get('event_type', '')}` "
                    f"status=`{event.get('status', '')}` "
                    f"params=`{event.get('params', {})}`"
                )
            lines.append("")
    lines.append("## 待关注事项")
    lines.append("")
    failed_events = [event for event in events if str(event.get("status") or "").strip() == "failed"]
    if failed_events:
        lines.append(f"- 今日有 {len(failed_events)} 条失败事件，优先复查日志和输入参数。")
    else:
        lines.append("- 今日未发现失败事件。")
    lines.append("- 可进一步把日报入库到平台运行记忆知识库。")

    return {
        "event_date": day,
        "total": len(events),
        "content": "\n".join(lines).strip() + "\n",
    }


def write_daily_report(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    output_path: Path | None = None,
) -> Path:
    payload = build_daily_report(root_dir, event_date=event_date, knowledge_base_id=knowledge_base_id)
    day = payload["event_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "daily" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload["content"], encoding="utf-8")
    return output_path
