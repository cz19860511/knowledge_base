from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


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


def get_confirmation_path(root_dir: Path | str, event_date: str | None = None) -> Path:
    day = event_date or _default_date()
    return Path(root_dir) / "operations" / "evolution_confirmations" / f"{day}.jsonl"


def record_evolution_confirmation(
    root_dir: Path | str,
    *,
    decision: str,
    suggestion: dict,
    decided_by: str,
    note: str = "",
    source_report_date: str = "",
    source_report_path: str = "",
    event_date: str | None = None,
) -> dict:
    payload = {
        "confirmation_id": f"ecf_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "decision": decision,
        "decided_by": decided_by,
        "decided_at": _now_iso(),
        "note": note,
        "source_report_date": source_report_date,
        "source_report_path": source_report_path,
        "suggestion": {
            "suggestion_id": str(suggestion.get("suggestion_id") or ""),
            "category": str(suggestion.get("category") or ""),
            "title": str(suggestion.get("title") or ""),
            "summary": str(suggestion.get("summary") or ""),
            "recommendation": str(suggestion.get("recommendation") or ""),
            "scope": str(suggestion.get("scope") or ""),
            "risk_level": str(suggestion.get("risk_level") or ""),
            "priority": int(suggestion.get("priority", 0) or 0),
            "requires_human_confirmation": bool(suggestion.get("requires_human_confirmation", True)),
            "related_event_types": list(suggestion.get("related_event_types") or []),
            "related_knowledge_base_ids": list(suggestion.get("related_knowledge_base_ids") or []),
            "evidence": list(suggestion.get("evidence") or []),
        },
    }
    _append_jsonl(get_confirmation_path(root_dir, event_date=event_date), payload)
    return payload


def list_evolution_confirmations(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    decision: str | None = None,
    limit: int = 500,
) -> dict:
    path = get_confirmation_path(root_dir, event_date=event_date)
    items = _read_jsonl(path)
    if decision:
        items = [item for item in items if str(item.get("decision") or "").strip() == decision]
    items = items[-limit:] if limit > 0 else items
    return {
        "total": len(items),
        "event_date": event_date or _default_date(),
        "confirmation_path": str(path),
        "items": items,
    }


def write_evolution_confirmation_report(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    output_path: Path | None = None,
) -> Path:
    payload = list_evolution_confirmations(root_dir, event_date=event_date)
    day = payload["event_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "evolution_confirmations" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for item in payload["items"]:
        decision = str(item.get("decision") or "unknown")
        counts[decision] = counts.get(decision, 0) + 1

    lines = [
        f"# 自进化建议人工确认记录 {day}",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- 记录总数：{payload['total']}",
        "",
        "## 决策统计",
        "",
    ]
    if counts:
        for decision, count in counts.items():
            lines.append(f"- {decision}: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 确认记录", ""])
    if payload["items"]:
        for item in payload["items"]:
            suggestion = item.get("suggestion", {})
            lines.append(
                f"- [{item.get('decided_at', '')}] `{item.get('decision', '')}` "
                f"{suggestion.get('title', '')} / kb=`{','.join(suggestion.get('related_knowledge_base_ids') or []) or '-'}` "
                f"by=`{item.get('decided_by', '')}` note=`{item.get('note', '')}`"
            )
    else:
        lines.append("- 无")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
