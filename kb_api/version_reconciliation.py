from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .asset_manifest import list_asset_versions
from .operation_log import list_operation_events


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_date() -> str:
    return datetime.now().date().isoformat()


def _norm(value: str | None) -> str:
    return str(value or "").strip()


def _asset_key(asset: dict) -> tuple[str, str]:
    return (_norm(asset.get("knowledge_base_id")), _norm(asset.get("file_path") or asset.get("logical_path")))


def _event_asset_refs(event: dict) -> list[dict]:
    refs: list[dict] = []
    for kind in ("input_assets", "output_assets"):
        for item in event.get(kind, []) or []:
            if not isinstance(item, dict):
                continue
            refs.append(item)
    return refs


def build_version_reconciliation(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    limit: int = 1000,
) -> dict:
    day = event_date or _default_date()
    events_payload = list_operation_events(root_dir, knowledge_base_id=knowledge_base_id, event_date=day, limit=limit)
    assets_payload = list_asset_versions(root_dir, knowledge_base_id=knowledge_base_id, limit=limit * 5)

    events = events_payload.get("items", [])
    assets = assets_payload.get("items", [])

    asset_by_path = {_asset_key(asset): asset for asset in assets if _asset_key(asset)[1]}
    linked_asset_ids: set[str] = set()
    missing_refs: list[dict] = []
    matched_refs: list[dict] = []

    for event in events:
        event_id = _norm(event.get("event_id"))
        event_type = _norm(event.get("event_type"))
        kb_id = _norm(event.get("knowledge_base_id"))
        for ref in _event_asset_refs(event):
            ref_path = _norm(ref.get("file_path") or ref.get("logical_path"))
            ref_kb = _norm(ref.get("kb_id") or kb_id)
            ref_stage = _norm(ref.get("stage"))
            candidate = asset_by_path.get((ref_kb, ref_path))
            if candidate is None:
                missing_refs.append(
                    {
                        "event_id": event_id,
                        "event_type": event_type,
                        "knowledge_base_id": ref_kb,
                        "stage": ref_stage,
                        "ref_path": ref_path,
                    }
                )
                continue
            linked_asset_ids.add(str(candidate.get("asset_id") or ""))
            matched_refs.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "knowledge_base_id": ref_kb,
                    "stage": ref_stage,
                    "ref_path": ref_path,
                    "asset_id": candidate.get("asset_id", ""),
                    "asset_type": candidate.get("asset_type", ""),
                    "version": candidate.get("version", ""),
                }
            )

    orphan_assets: list[dict] = []
    for asset in assets:
        if str(asset.get("asset_id") or "") in linked_asset_ids:
            continue
        orphan_assets.append(
            {
                "asset_id": asset.get("asset_id", ""),
                "knowledge_base_id": asset.get("knowledge_base_id", ""),
                "asset_type": asset.get("asset_type", ""),
                "stage": asset.get("stage", ""),
                "logical_path": asset.get("logical_path", ""),
                "version": asset.get("version", ""),
                "created_at": asset.get("created_at", ""),
            }
        )

    report = {
        "report_date": day,
        "generated_at": _now_iso(),
        "event_total": len(events),
        "asset_total": len(assets),
        "linked_ref_total": len(matched_refs),
        "missing_ref_total": len(missing_refs),
        "orphan_asset_total": len(orphan_assets),
        "events": events,
        "matched_refs": matched_refs,
        "missing_refs": missing_refs,
        "orphan_assets": orphan_assets,
        "event_log_path": str(Path(root_dir) / "operations" / "events" / f"{day}.jsonl"),
        "asset_manifest_path": str(Path(root_dir) / "operations" / "asset_manifest.json"),
    }
    return report


def write_version_reconciliation(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    output_path: Path | None = None,
) -> Path:
    payload = build_version_reconciliation(root_dir, event_date=event_date, knowledge_base_id=knowledge_base_id)
    day = payload["report_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "reconciliation" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# 版本对账报告 {day}",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- 事件总数：{payload['event_total']}",
        f"- 资产总数：{payload['asset_total']}",
        f"- 已关联引用：{payload['linked_ref_total']}",
        f"- 缺失引用：{payload['missing_ref_total']}",
        f"- 孤儿资产：{payload['orphan_asset_total']}",
        "",
        "## 对账摘要",
        "",
        "```json",
        json.dumps(
            {
                "report_date": payload["report_date"],
                "event_total": payload["event_total"],
                "asset_total": payload["asset_total"],
                "linked_ref_total": payload["linked_ref_total"],
                "missing_ref_total": payload["missing_ref_total"],
                "orphan_asset_total": payload["orphan_asset_total"],
                "event_log_path": payload["event_log_path"],
                "asset_manifest_path": payload["asset_manifest_path"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
    ]

    if payload["missing_refs"]:
        lines.extend(["## 缺失引用", ""])
        for item in payload["missing_refs"][:50]:
            lines.append(
                f"- {item['event_type']} / kb={item['knowledge_base_id']} / stage={item['stage']} / ref={item['ref_path'] or '-'}"
            )
        lines.append("")

    if payload["orphan_assets"]:
        lines.extend(["## 孤儿资产", ""])
        for item in payload["orphan_assets"][:50]:
            lines.append(
                f"- {item['asset_type']} / kb={item['knowledge_base_id']} / stage={item['stage']} / path={item['logical_path']}"
            )
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
