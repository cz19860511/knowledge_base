from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .operation_log import list_operation_events


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_date() -> str:
    return datetime.now().date().isoformat()


def _suggestion(
    *,
    category: str,
    title: str,
    summary: str,
    recommendation: str,
    evidence: list[str] | None = None,
    scope: str = "",
    risk_level: str = "medium",
    priority: int = 3,
    requires_human_confirmation: bool = True,
    related_event_types: list[str] | None = None,
    related_knowledge_base_ids: list[str] | None = None,
) -> dict:
    return {
        "suggestion_id": f"evs_{uuid4().hex}",
        "category": category,
        "title": title,
        "summary": summary,
        "recommendation": recommendation,
        "evidence": evidence or [],
        "scope": scope,
        "risk_level": risk_level,
        "priority": priority,
        "requires_human_confirmation": requires_human_confirmation,
        "related_event_types": related_event_types or [],
        "related_knowledge_base_ids": related_knowledge_base_ids or [],
    }


def _event_label(event: dict) -> str:
    started = str(event.get("started_at") or "").strip()
    event_type = str(event.get("event_type") or "unknown").strip() or "unknown"
    status = str(event.get("status") or "unknown").strip() or "unknown"
    kb_id = str(event.get("knowledge_base_id") or "platform").strip() or "platform"
    remark = str(event.get("remark") or "").strip()
    pieces = [started, event_type, f"kb={kb_id}", f"status={status}"]
    if remark:
        pieces.append(f"remark={remark}")
    return " | ".join(piece for piece in pieces if piece)


def _top_kb_ids(events: list[dict]) -> list[str]:
    counts = Counter(str(event.get("knowledge_base_id") or "platform").strip() or "platform" for event in events)
    return [kb_id for kb_id, _ in counts.most_common(3)]


def build_evolution_templates() -> dict:
    return {
        "template_pack_id": "evolution_suggestion_templates_v1",
        "generated_at": _now_iso(),
        "templates": [
            {
                "template_id": "optimize_parameters",
                "category": "pipeline_stability",
                "title": "参数优化建议模板",
                "when_to_use": "当 chunk 质量、embedding 命中率或检索排序出现波动时使用。",
                "required_inputs": [
                    "最近一段时间的失败事件",
                    "当前流程配置快照",
                    "相关知识库 ID",
                    "检索问题或命中样例",
                ],
                "output_fields": [
                    "问题描述",
                    "可调参数",
                    "建议调整方向",
                    "风险提示",
                    "验证方式",
                ],
                "prompt_template": "请结合最新操作事件、流程配置和检索样例，判断哪些参数需要调整，并给出最小变更建议、风险和验证方式。",
            },
            {
                "template_id": "rollback_action",
                "category": "data_governance",
                "title": "回滚建议模板",
                "when_to_use": "当原始文件传错、预处理异常或新版本明显劣化时使用。",
                "required_inputs": [
                    "出问题的文件或批次",
                    "当前版本与上一版本对比",
                    "回滚记录",
                    "关联操作事件",
                ],
                "output_fields": [
                    "回滚对象",
                    "回滚原因",
                    "推荐回滚到的版本",
                    "影响范围",
                    "人工确认项",
                ],
                "prompt_template": "请基于版本历史和操作事件判断是否需要回滚，若需要请明确回滚对象、推荐版本、影响范围和确认项。",
            },
            {
                "template_id": "supplement_data",
                "category": "knowledge_base_governance",
                "title": "补资料建议模板",
                "when_to_use": "当问题命中不足、场景覆盖不全或规则无法支撑回答时使用。",
                "required_inputs": [
                    "未命中的问题列表",
                    "当前知识库覆盖范围",
                    "高频失败场景",
                    "相关业务模块",
                ],
                "output_fields": [
                    "缺口场景",
                    "需要补充的资料类型",
                    "建议责任人/来源",
                    "优先级",
                    "补齐后验证方式",
                ],
                "prompt_template": "请根据未命中问题和运行事件，识别知识缺口并给出需要补充的资料类型、优先级和验证方式。",
            },
        ],
    }


def build_evolution_suggestions(
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
    kb_ids = _top_kb_ids(events)

    failed_events = [event for event in events if str(event.get("status") or "").strip() == "failed"]
    pipeline_failed = [event for event in failed_events if str(event.get("event_type") or "").strip() in {"pipeline", "preprocess", "chunk", "embedding"}]
    raw_changes = [event for event in events if str(event.get("event_type") or "").strip() in {"upload", "delete", "rollback"}]
    kb_events = [event for event in events if str(event.get("event_type") or "").strip().startswith("knowledge_base_")]
    memory_events = [event for event in events if str(event.get("event_type") or "").strip().startswith("daily_report_")]

    summary_lines = [
        f"今日共记录 {len(events)} 条事件，失败 {len(failed_events)} 条，涉及 {len(kb_ids)} 个知识库/平台域。",
    ]
    if failed_events:
        summary_lines.append("存在失败事件，建议优先复查输入参数、脚本日志和任务状态。")
    if raw_changes:
        summary_lines.append(f"原始文件变更 {len(raw_changes)} 条，建议同步检查版本历史和回滚可用性。")
    if kb_events:
        summary_lines.append(f"知识库管理事件 {len(kb_events)} 条，建议确认切库和初始化是否留下了预期目录。")
    if memory_events:
        summary_lines.append(f"日报/运行记忆相关事件 {len(memory_events)} 条，建议确认自动调度稳定性。")
    summary = " ".join(summary_lines)

    suggestions: list[dict] = []

    if failed_events:
        suggestions.append(
            _suggestion(
                category="pipeline_stability",
                title="先复查失败事件和对应日志",
                summary=f"本日有 {len(failed_events)} 条失败事件，优先定位失败步骤、输入参数和日志路径。",
                recommendation="按失败事件的时间顺序逐条查看事件日志、流水线日志和输入资产，先确认是不是配置问题、文件缺失或版本冲突。",
                evidence=[_event_label(event) for event in failed_events[:8]],
                scope="平台运行层 / 预处理 / chunk / embedding",
                risk_level="high",
                priority=1,
                related_event_types=[str(event.get("event_type") or "").strip() for event in failed_events if str(event.get("event_type") or "").strip()],
                related_knowledge_base_ids=kb_ids,
            )
        )

    if pipeline_failed:
        suggestions.append(
            _suggestion(
                category="pipeline_stability",
                title="检查预处理到向量构建链路是否稳定",
                summary=f"本日有 {len(pipeline_failed)} 条流水线失败事件，建议优先确认 MinerU、chunk 和 embedding 的配置是否一致。",
                recommendation="核对流程配置页中的预处理、chunk、embedding 参数，并检查该批次的原始文件是否存在格式异常、目录遗漏或模型加载异常。",
                evidence=[_event_label(event) for event in pipeline_failed[:6]],
                scope="预处理 / chunk / embedding",
                risk_level="high",
                priority=1,
                related_event_types=[str(event.get("event_type") or "").strip() for event in pipeline_failed if str(event.get("event_type") or "").strip()],
                related_knowledge_base_ids=kb_ids,
            )
        )

    if raw_changes:
        suggestions.append(
            _suggestion(
                category="data_governance",
                title="检查原始文件版本和回滚台账",
                summary=f"原始文件变更 {len(raw_changes)} 条，说明当天资料更新较活跃，建议确认版本历史和回滚路径是否完整。",
                recommendation="抽查几份最近变更的文件，确认版本号、checksum、回滚上一版以及历史展开都正确记录，避免未来误传文件难以恢复。",
                evidence=[_event_label(event) for event in raw_changes[:6]],
                scope="原始文件管理",
                risk_level="medium",
                priority=2,
                related_event_types=[str(event.get("event_type") or "").strip() for event in raw_changes if str(event.get("event_type") or "").strip()],
                related_knowledge_base_ids=kb_ids,
            )
        )

    if kb_events:
        suggestions.append(
            _suggestion(
                category="knowledge_base_governance",
                title="确认知识库切换和初始化后的目录隔离",
                summary=f"知识库事件 {len(kb_events)} 条，说明当日有新增、切换或初始化动作，建议确认目录隔离是否按预期生效。",
                recommendation="复查新知识库的 root_dir、selected/chunks/vectors 目录和注册表状态，确认不会与主库互相串库。",
                evidence=[_event_label(event) for event in kb_events[:6]],
                scope="知识库管理",
                risk_level="medium",
                priority=2,
                related_event_types=[str(event.get("event_type") or "").strip() for event in kb_events if str(event.get("event_type") or "").strip()],
                related_knowledge_base_ids=kb_ids,
            )
        )

    if memory_events:
        suggestions.append(
            _suggestion(
                category="memory_sync",
                title="确认日报自动调度和运行记忆入库链路",
                summary=f"日报/运行记忆相关事件 {len(memory_events)} 条，建议确认自动生成、自动入库和后台调度都正常。",
                recommendation="检查每天的日报是否都生成到 operations/daily，并确认 platform_run_memory 的 selected/chunks/vectors 产物都有更新。",
                evidence=[_event_label(event) for event in memory_events[:6]],
                scope="日报自动调度 / 平台运行记忆库",
                risk_level="medium",
                priority=2,
                related_event_types=[str(event.get("event_type") or "").strip() for event in memory_events if str(event.get("event_type") or "").strip()],
                related_knowledge_base_ids=["platform_run_memory"],
            )
        )

    if not suggestions and events:
        suggestions.append(
            _suggestion(
                category="platform_health",
                title="当前没有明显异常，建议保持回归观察",
                summary="今天的事件没有暴露出明显失败或高风险变更，可以继续关注后续几天的趋势。",
                recommendation="继续按当前流程运行，并在日终报告里观察失败率、变更频率和回滚数量是否上升。",
                evidence=[_event_label(event) for event in events[:5]],
                scope="平台整体",
                risk_level="low",
                priority=4,
                related_event_types=list(event_types.keys()),
                related_knowledge_base_ids=kb_ids,
            )
        )

    if not events:
        suggestions.append(
            _suggestion(
                category="platform_health",
                title="今日暂无事件，建议确认自动调度是否已启用",
                summary="当前没有操作事件，可能是系统确实空闲，也可能是自动调度或记录链路尚未启动。",
                recommendation="先确认自动调度状态和操作事件接口是否都有记录，再决定是否需要人工补跑日报。",
                evidence=["今日无操作事件记录"],
                scope="平台整体",
                risk_level="low",
                priority=5,
                related_event_types=[],
                related_knowledge_base_ids=[],
            )
        )

    return {
        "report_date": day,
        "total_events": len(events),
        "total_suggestions": len(suggestions),
        "summary": summary,
        "suggestions": suggestions,
    }


def get_evolution_templates() -> dict:
    return build_evolution_templates()


def write_evolution_report(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    knowledge_base_id: str | None = None,
    output_path: Path | None = None,
) -> Path:
    payload = build_evolution_suggestions(root_dir, event_date=event_date, knowledge_base_id=knowledge_base_id)
    day = payload["report_date"]
    if output_path is None:
        output_path = Path(root_dir) / "operations" / "evolution" / f"{day}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# 知识平台自进化建议 {day}",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- 事件总数：{payload['total_events']}",
        f"- 建议总数：{payload['total_suggestions']}",
        "",
        "## 平台状态总结",
        "",
        payload["summary"],
        "",
        "## 建议清单",
        "",
    ]

    for idx, item in enumerate(payload["suggestions"], start=1):
        lines.extend(
            [
                f"### {idx}. [{item['risk_level']}] {item['title']}",
                "",
                f"- 类别：{item['category']}",
                f"- 优先级：{item['priority']}",
                f"- 范围：{item['scope'] or '-'}",
                f"- 需要人工确认：{'是' if item['requires_human_confirmation'] else '否'}",
                f"- 摘要：{item['summary']}",
                f"- 建议：{item['recommendation']}",
                "- 证据：",
            ]
        )
        if item["evidence"]:
            lines.extend([f"  - {e}" for e in item["evidence"]])
        else:
            lines.append("  - 无")
        lines.append("")

    import json

    lines.extend(
        [
            "## 结构化数据",
            "",
            "```json",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
