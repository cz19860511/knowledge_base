from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .asset_manifest import list_asset_versions
from .daily_report import build_daily_report
from .operation_log import list_operation_events
from .version_reconciliation import build_version_reconciliation


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_date() -> str:
    return datetime.now().date().isoformat()


def _label(event: dict) -> str:
    started = str(event.get("started_at") or "").strip()
    event_type = str(event.get("event_type") or "unknown").strip() or "unknown"
    status = str(event.get("status") or "unknown").strip() or "unknown"
    kb_id = str(event.get("knowledge_base_id") or "platform").strip() or "platform"
    return f"{started} | {event_type} | kb={kb_id} | status={status}"


def build_replay_report(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    limit: int = 5000,
) -> dict:
    day = event_date or _default_date()
    events_payload = list_operation_events(root_dir, knowledge_base_id=knowledge_base_id, event_date=day, limit=limit)
    events = events_payload.get("items", [])
    daily_report = build_daily_report(root_dir, event_date=day, knowledge_base_id=knowledge_base_id, limit=limit)
    reconciliation = build_version_reconciliation(root_dir, event_date=day, knowledge_base_id=knowledge_base_id, limit=limit)
    assets_payload = list_asset_versions(root_dir, knowledge_base_id=knowledge_base_id, limit=limit)

    event_types = Counter(str(item.get("event_type") or "").strip() or "unknown" for item in events)
    statuses = Counter(str(item.get("status") or "").strip() or "unknown" for item in events)
    grouped_by_kb: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        kb_id = str(event.get("knowledge_base_id") or "platform").strip() or "platform"
        grouped_by_kb[kb_id].append(event)

    timeline = [
        {
            "event_id": item.get("event_id", ""),
            "started_at": item.get("started_at", ""),
            "event_type": item.get("event_type", ""),
            "knowledge_base_id": item.get("knowledge_base_id", ""),
            "status": item.get("status", ""),
            "source": item.get("source", ""),
            "remark": item.get("remark", ""),
        }
        for item in events
    ]
    timeline.sort(key=lambda row: str(row.get("started_at") or ""))

    summary = [
        f"今日共发生 {len(events)} 条事件，覆盖 {len(grouped_by_kb)} 个知识库/平台域。",
        f"其中失败 {statuses.get('failed', 0)} 条，成功 {statuses.get('success', 0)} 条。",
    ]
    if reconciliation["missing_ref_total"]:
        summary.append(f"存在 {reconciliation['missing_ref_total']} 条缺失引用，建议先查资产版本链。")
    if reconciliation["orphan_asset_total"]:
        summary.append(f"存在 {reconciliation['orphan_asset_total']} 条孤儿资产，建议核对事件是否漏记。")
    if not events:
        summary.append("今日没有操作事件，可确认自动调度或记录链路是否正常。")

    return {
        "report_date": day,
        "generated_at": _now_iso(),
        "event_total": len(events),
        "asset_total": assets_payload.get("total", 0),
        "summary": " ".join(summary),
        "timeline": timeline,
        "events": events,
        "daily_report": daily_report,
        "reconciliation": reconciliation,
        "event_types": dict(event_types),
        "statuses": dict(statuses),
        "grouped_by_kb": grouped_by_kb,
        "asset_manifest_path": assets_payload.get("manifest_path", ""),
    }


def write_replay_report(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    output_path: Path | None = None,
) -> Path:
    payload = build_replay_report(root_dir, event_date=event_date, knowledge_base_id=knowledge_base_id)
    day = payload["report_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "replay" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# 平台事件回放 {day}",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- 事件总数：{payload['event_total']}",
        f"- 资产总数：{payload['asset_total']}",
        "",
        "## 回放摘要",
        "",
        payload["summary"],
        "",
        "## 事件时间线",
        "",
    ]
    if not payload["timeline"]:
        lines.append("- 无")
    else:
        for item in payload["timeline"][:200]:
            lines.append(
                f"- [{item['started_at']}] `{item['event_type']}` "
                f"kb=`{item['knowledge_base_id']}` status=`{item['status']}` "
                f"source=`{item['source']}` remark=`{item['remark']}`"
            )
    lines.extend(
        [
            "",
            "## 事件类型统计",
            "",
        ]
    )
    for event_type, count in sorted(payload["event_types"].items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {event_type}: {count}")
    if not payload["event_types"]:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 知识库分组",
            "",
        ]
    )
    for kb_id, kb_events in payload["grouped_by_kb"].items():
        lines.append(f"### {kb_id}")
        for event in kb_events[-20:]:
            lines.append(
                f"- `{event.get('event_type', '')}` status=`{event.get('status', '')}` "
                f"params=`{event.get('params', {})}`"
            )
        lines.append("")

    lines.extend(
        [
            "## 当日报告",
            "",
            payload["daily_report"]["content"].strip(),
            "",
            "## 版本对账摘要",
            "",
            "```json",
            json.dumps(
                {
                    "event_total": payload["reconciliation"]["event_total"],
                    "asset_total": payload["reconciliation"]["asset_total"],
                    "linked_ref_total": payload["reconciliation"]["linked_ref_total"],
                    "missing_ref_total": payload["reconciliation"]["missing_ref_total"],
                    "orphan_asset_total": payload["reconciliation"]["orphan_asset_total"],
                    "asset_manifest_path": payload["asset_manifest_path"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
