from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .daily_report import build_daily_report, write_daily_report
from .daily_memory import ingest_daily_report_to_memory
from .asset_manifest import list_asset_versions
from .evolution import build_evolution_suggestions, get_evolution_templates, write_evolution_report
from .evolution_confirmation import list_evolution_confirmations, record_evolution_confirmation, write_evolution_confirmation_report
from .replay import build_replay_report, write_replay_report
from .platform_tasks import build_task_history_report, build_task_report, create_platform_task, create_platform_task_from_confirmation, list_platform_tasks, update_platform_task, write_task_history_report, write_task_report
from .platform_tasks import get_platform_task, get_task_history_path, transition_platform_task
from .version_reconciliation import build_version_reconciliation, write_version_reconciliation
from .daily_report_scheduler import ensure_daily_report_scheduler_started, load_daily_report_automation_status, run_daily_report_automation
from .operation_log import append_operation_event, list_operation_events
from .rag import load_chunks, search
from .raw_store import delete_raw_file, get_pipeline_status, list_raw_files, rollback_raw_file, save_uploaded_files, start_pipeline
from .schemas import (
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseRegistryResponse,
    KnowledgeBaseRegistryUpsertRequest,
    DailyReportResponse,
    DailyReportIngestResponse,
    DailyReportAutomationStatusResponse,
    DailyReportAutomationRunResponse,
    EvolutionSuggestionResponse,
    EvolutionTemplatesResponse,
    EvolutionReportResponse,
    EvolutionConfirmationCreateRequest,
    EvolutionConfirmationListResponse,
    EvolutionConfirmationRecord,
    EvolutionConfirmationReportResponse,
    PlatformTask,
    PlatformTaskCreateRequest,
    PlatformTaskDetailResponse,
    PlatformTaskHistoryResponse,
    PlatformTaskHistoryReportResponse,
    PlatformTaskListResponse,
    PlatformTaskReportResponse,
    PlatformTaskUpdateRequest,
    PlatformTaskTransitionRequest,
    AssetManifestResponse,
    VersionReconciliationResponse,
    ReplayReportResponse,
    RawDeleteResponse,
    RawFileListResponse,
    RawPipelineResponse,
    RawPipelineStatus,
    RawUploadResponse,
    RawRollbackResponse,
    PipelineConfigResponse,
    PipelineConfigUpdateRequest,
    OperationEventListResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from knowledge_base_registry import delete_registry_item, get_active_registry_item, get_registry_path, load_registry, set_active_registry_item, upsert_registry_item
from knowledge_base_paths import ensure_knowledge_base_workspace, resolve_knowledge_base_id_for_request
from pipeline_config import DEFAULT_PIPELINE_CONFIG, get_pipeline_config_path, load_pipeline_config, normalize_pipeline_config, save_pipeline_config


app = FastAPI(title="kb-api", version="0.1.0")
WEBUI_DIR = Path(__file__).resolve().parent / "webui"

if WEBUI_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEBUI_DIR), name="webui-assets")


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


@app.get("/health")
def health() -> dict:
    pipeline_config = load_pipeline_config(settings.root_dir)
    active_kb = get_active_registry_item(settings.root_dir)
    return {
        "status": "ok",
        "knowledge_base_id": active_kb.get("knowledge_base_id", settings.knowledge_base_id),
        "active_knowledge_base_id": active_kb.get("knowledge_base_id", settings.knowledge_base_id),
        "batch_id": settings.batch_id,
        "retrieval_mode": settings.retrieval_mode,
        "embedding_model": pipeline_config.get("embedding", {}).get("model_name", settings.embedding_model_name),
    }


@app.on_event("startup")
def startup() -> None:
    ensure_daily_report_scheduler_started(settings.root_dir)


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def webui() -> FileResponse:
    return FileResponse(WEBUI_DIR / "index.html")


@app.get("/raw-files-ui", include_in_schema=False)
@app.get("/raw-ui", include_in_schema=False)
def raw_webui() -> FileResponse:
    return FileResponse(WEBUI_DIR / "raw-files.html")


@app.get("/pipeline-config-ui", include_in_schema=False)
def pipeline_config_webui() -> FileResponse:
    return FileResponse(WEBUI_DIR / "pipeline-config.html")


@app.get("/knowledge-base-manager-ui", include_in_schema=False)
def knowledge_base_manager_webui() -> FileResponse:
    return FileResponse(WEBUI_DIR / "knowledge-base-manager.html")


@app.get("/platform-overview-ui", include_in_schema=False)
def platform_overview_webui() -> FileResponse:
    return FileResponse(WEBUI_DIR / "platform-overview.html")


@app.get("/platform-tasks-ui", include_in_schema=False)
def platform_tasks_webui() -> FileResponse:
    return FileResponse(WEBUI_DIR / "platform-tasks.html")


@app.get("/knowledge-bases", response_model=KnowledgeBaseListResponse, dependencies=[Depends(require_api_key)])
def list_knowledge_bases() -> KnowledgeBaseListResponse:
    chunks = load_chunks()
    registry = load_registry(settings.root_dir)
    items: list[KnowledgeBaseItem] = []
    for item in registry.get("items", []):
        if not isinstance(item, dict):
            continue
        kb_id = str(item.get("knowledge_base_id") or "").strip()
        if not kb_id:
            continue
        doc_count = int(item.get("doc_count", 0) or 0)
        chunk_count = int(item.get("chunk_count", 0) or 0)
        if kb_id == registry.get("active_knowledge_base_id", settings.knowledge_base_id):
            doc_count = len({row["doc_id"] for row in chunks})
            chunk_count = len(chunks)
        items.append(
            KnowledgeBaseItem(
                knowledge_base_id=kb_id,
                name=str(item.get("name") or kb_id),
                description=str(item.get("description") or ""),
                doc_count=doc_count,
                chunk_count=chunk_count,
            )
        )
    if not items:
        items = [
            KnowledgeBaseItem(
                knowledge_base_id=settings.knowledge_base_id,
                name="AI+智能问答智能体标准库",
                description="本地知识库经由 General 接口适配后供 AgentArts 调用。",
                doc_count=len({row["doc_id"] for row in chunks}),
                chunk_count=len(chunks),
            )
        ]
    return KnowledgeBaseListResponse(
        total=len(items),
        knowledge_base_list=items,
    )


@app.get("/knowledge-base-registry", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def get_knowledge_base_registry() -> KnowledgeBaseRegistryResponse:
    registry = load_registry(settings.root_dir)
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.post("/knowledge-base-registry", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def create_or_update_knowledge_base_registry(req: KnowledgeBaseRegistryUpsertRequest) -> KnowledgeBaseRegistryResponse:
    registry = upsert_registry_item(settings.root_dir, req.model_dump())
    append_operation_event(
        settings.root_dir,
        event_type="knowledge_base_upsert",
        knowledge_base_id=req.knowledge_base_id,
        source="api/knowledge-base-registry",
        actor="webui",
        params=req.model_dump(),
        status="success",
        remark="knowledge base registry upserted",
    )
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.put("/knowledge-base-registry/{knowledge_base_id}", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def update_knowledge_base_registry(knowledge_base_id: str, req: KnowledgeBaseRegistryUpsertRequest) -> KnowledgeBaseRegistryResponse:
    payload = req.model_dump()
    payload["knowledge_base_id"] = knowledge_base_id
    registry = upsert_registry_item(settings.root_dir, payload)
    append_operation_event(
        settings.root_dir,
        event_type="knowledge_base_update",
        knowledge_base_id=knowledge_base_id,
        source="api/knowledge-base-registry",
        actor="webui",
        params=payload,
        status="success",
        remark="knowledge base registry updated",
    )
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.delete("/knowledge-base-registry/{knowledge_base_id}", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def delete_knowledge_base_registry(knowledge_base_id: str) -> KnowledgeBaseRegistryResponse:
    registry = delete_registry_item(settings.root_dir, knowledge_base_id)
    append_operation_event(
        settings.root_dir,
        event_type="knowledge_base_delete",
        knowledge_base_id=knowledge_base_id,
        source="api/knowledge-base-registry",
        actor="webui",
        params={"knowledge_base_id": knowledge_base_id},
        status="success",
        remark="knowledge base registry deleted",
    )
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.post("/knowledge-base-registry/{knowledge_base_id}/activate", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def activate_knowledge_base_registry(knowledge_base_id: str) -> KnowledgeBaseRegistryResponse:
    registry = set_active_registry_item(settings.root_dir, knowledge_base_id)
    append_operation_event(
        settings.root_dir,
        event_type="knowledge_base_activate",
        knowledge_base_id=knowledge_base_id,
        source="api/knowledge-base-registry",
        actor="webui",
        params={"knowledge_base_id": knowledge_base_id},
        status="success",
        remark="knowledge base activated",
    )
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.post("/knowledge-base-registry/{knowledge_base_id}/initialize", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def initialize_knowledge_base_registry(knowledge_base_id: str) -> KnowledgeBaseRegistryResponse:
    registry = load_registry(settings.root_dir)
    item = next((row for row in registry.get("items", []) if row.get("knowledge_base_id") == knowledge_base_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"knowledge base not found: {knowledge_base_id}")

    paths = ensure_knowledge_base_workspace(settings.root_dir, knowledge_base_id)
    config_path = paths["operations_dir"] / "pipeline_config.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps(normalize_pipeline_config(DEFAULT_PIPELINE_CONFIG), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    payload = dict(item)
    payload["doc_count"] = int(item.get("doc_count", 0) or 0)
    payload["chunk_count"] = int(item.get("chunk_count", 0) or 0)
    registry = upsert_registry_item(settings.root_dir, payload)
    append_operation_event(
        settings.root_dir,
        event_type="knowledge_base_initialize",
        knowledge_base_id=knowledge_base_id,
        source="api/knowledge-base-registry",
        actor="webui",
        params={"knowledge_base_id": knowledge_base_id, "root_dir": str(paths["root_dir"])},
        status="success",
        remark="knowledge base workspace initialized",
    )
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.post("/knowledge-bases/retrieve", response_model=RetrieveResponse, dependencies=[Depends(require_api_key)])
def retrieve(req: RetrieveRequest) -> RetrieveResponse:
    try:
        target_kb_id = resolve_knowledge_base_id_for_request(
            settings.root_dir,
            knowledge_base_id=req.knowledge_base_id,
            knowledge_base_ids=req.knowledge_base_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    top_k = req.top_k or settings.top_k_default
    threshold = req.search_threshold if req.search_threshold is not None else settings.search_threshold
    hits = search(req.query, top_k=top_k, threshold=threshold, knowledge_base_id=target_kb_id)
    return RetrieveResponse(
        search_result_list=[
            {
                **hit,
                "content": hit["content"][:4000],
            }
            for hit in hits[req.offset : req.offset + req.limit]
        ],
        total=len(hits),
    )


@app.get("/raw-files", response_model=RawFileListResponse, dependencies=[Depends(require_api_key)])
def raw_files(include_deleted: bool = Query(default=False)) -> RawFileListResponse:
    payload = list_raw_files(include_deleted=include_deleted)
    return RawFileListResponse(**payload)


@app.post("/raw-files/upload", response_model=RawUploadResponse, dependencies=[Depends(require_api_key)])
def upload_raw_files(
    folder: str = Form(...),
    files: list[UploadFile] = File(...),
    run_pipeline: bool = Form(default=False),
) -> RawUploadResponse:
    payload = save_uploaded_files(folder=folder, uploads=files)
    pipeline_status = None
    pipeline_started = False
    if run_pipeline:
        pipeline_status = start_pipeline(trigger_reason=f"upload:{folder}")
        pipeline_started = bool(pipeline_status.get("running"))
    return RawUploadResponse(
        **payload,
        pipeline_started=pipeline_started,
        pipeline_status=pipeline_status,
    )


@app.delete("/raw-files", response_model=RawDeleteResponse, dependencies=[Depends(require_api_key)])
def remove_raw_file(
    folder: str = Query(...),
    file_name: str = Query(...),
    run_pipeline: bool = Query(default=False),
) -> RawDeleteResponse:
    payload = delete_raw_file(folder=folder, file_name=file_name)
    if run_pipeline:
        start_pipeline(trigger_reason=f"delete:{folder}")
    return RawDeleteResponse(**payload)


@app.post("/raw-files/rollback", response_model=RawRollbackResponse, dependencies=[Depends(require_api_key)])
def rollback_raw_file_api(
    folder: str = Query(...),
    file_name: str = Query(...),
    version: str | None = Query(default=None),
) -> RawRollbackResponse:
    payload = rollback_raw_file(folder=folder, file_name=file_name, version=version)
    return RawRollbackResponse(**payload)


@app.get("/raw-files/pipeline", response_model=RawPipelineStatus, dependencies=[Depends(require_api_key)])
def raw_pipeline_status() -> RawPipelineStatus:
    return RawPipelineStatus(**get_pipeline_status())


@app.get("/operations/events", response_model=OperationEventListResponse, dependencies=[Depends(require_api_key)])
def operation_events(
    date: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    knowledge_base_id: str | None = Query(default=None),
) -> OperationEventListResponse:
    payload = list_operation_events(settings.root_dir, knowledge_base_id=knowledge_base_id, event_date=date, limit=limit)
    return OperationEventListResponse(**payload)


@app.get("/operations/daily-report", response_model=DailyReportResponse, dependencies=[Depends(require_api_key)])
def daily_report(
    date: str | None = Query(default=None),
    knowledge_base_id: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> DailyReportResponse:
    payload = build_daily_report(settings.root_dir, event_date=date, knowledge_base_id=knowledge_base_id)
    report_path = ""
    if save:
        report_path = str(write_daily_report(settings.root_dir, event_date=payload["event_date"], knowledge_base_id=knowledge_base_id))
    return DailyReportResponse(
        report_path=report_path,
        event_date=payload["event_date"],
        total=payload["total"],
        content=payload["content"],
    )


@app.post("/operations/daily-report/ingest", response_model=DailyReportIngestResponse, dependencies=[Depends(require_api_key)])
def ingest_daily_report(
    date: str | None = Query(default=None),
) -> DailyReportIngestResponse:
    payload = ingest_daily_report_to_memory(settings.root_dir, event_date=date, save_report=True)
    return DailyReportIngestResponse(**payload)


@app.get("/operations/evolution-suggestions", response_model=EvolutionSuggestionResponse, dependencies=[Depends(require_api_key)])
def evolution_suggestions(
    date: str | None = Query(default=None),
    knowledge_base_id: str | None = Query(default=None),
) -> EvolutionSuggestionResponse:
    payload = build_evolution_suggestions(settings.root_dir, event_date=date, knowledge_base_id=knowledge_base_id)
    return EvolutionSuggestionResponse(**payload)


@app.get("/operations/evolution-templates", response_model=EvolutionTemplatesResponse, dependencies=[Depends(require_api_key)])
def evolution_templates() -> EvolutionTemplatesResponse:
    payload = get_evolution_templates()
    return EvolutionTemplatesResponse(**payload)


@app.get("/operations/evolution-report", response_model=EvolutionReportResponse, dependencies=[Depends(require_api_key)])
def evolution_report(
    date: str | None = Query(default=None),
    knowledge_base_id: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> EvolutionReportResponse:
    payload = build_evolution_suggestions(settings.root_dir, event_date=date, knowledge_base_id=knowledge_base_id)
    report_path = ""
    if save:
        report_path = str(write_evolution_report(settings.root_dir, event_date=payload["report_date"], knowledge_base_id=knowledge_base_id))
    return EvolutionReportResponse(
        report_path=report_path,
        event_date=payload["report_date"],
        total_events=payload["total_events"],
        total_suggestions=payload["total_suggestions"],
        content=payload["summary"],
    )


@app.get("/operations/evolution-confirmations", response_model=EvolutionConfirmationListResponse, dependencies=[Depends(require_api_key)])
def evolution_confirmations(
    date: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
) -> EvolutionConfirmationListResponse:
    payload = list_evolution_confirmations(settings.root_dir, event_date=date, decision=decision, limit=limit)
    return EvolutionConfirmationListResponse(**payload)


@app.post("/operations/evolution-confirmations", response_model=EvolutionConfirmationRecord, dependencies=[Depends(require_api_key)])
def create_evolution_confirmation(req: EvolutionConfirmationCreateRequest) -> EvolutionConfirmationRecord:
    payload = record_evolution_confirmation(
        settings.root_dir,
        decision=req.decision,
        decided_by=req.decided_by,
        note=req.note,
        source_report_date=req.source_report_date,
        source_report_path=req.source_report_path,
        suggestion=req.suggestion.model_dump(),
    )
    return EvolutionConfirmationRecord(**payload)


@app.get("/operations/evolution-confirmation-report", response_model=EvolutionConfirmationReportResponse, dependencies=[Depends(require_api_key)])
def evolution_confirmation_report(
    date: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> EvolutionConfirmationReportResponse:
    payload = list_evolution_confirmations(settings.root_dir, event_date=date)
    report_path = ""
    if save:
        report_path = str(write_evolution_confirmation_report(settings.root_dir, event_date=payload["event_date"]))
    content = "\n".join(
        [
            f"记录总数：{payload['total']}",
            f"确认文件：{payload['confirmation_path']}",
        ]
    )
    return EvolutionConfirmationReportResponse(
        report_path=report_path,
        event_date=payload["event_date"],
        total=payload["total"],
        content=content,
    )


@app.get("/operations/platform-tasks", response_model=PlatformTaskListResponse, dependencies=[Depends(require_api_key)])
def platform_tasks(
    date: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
) -> PlatformTaskListResponse:
    payload = list_platform_tasks(settings.root_dir, event_date=date, status=status, source_type=source_type, limit=limit)
    return PlatformTaskListResponse(**payload)


@app.post("/operations/platform-tasks", response_model=PlatformTask, dependencies=[Depends(require_api_key)])
def create_platform_task_endpoint(req: PlatformTaskCreateRequest) -> PlatformTask:
    payload = create_platform_task(
        settings.root_dir,
        title=req.title,
        summary=req.summary,
        priority=req.priority,
        status=req.status,
        owner=req.owner,
        due_date=req.due_date,
        source_type=req.source_type,
        source_id=req.source_id,
        source_report_date=req.source_report_date,
        source_report_path=req.source_report_path,
        source_payload=req.source_payload,
        created_by=req.created_by,
        note=req.note,
    )
    return PlatformTask(**payload)


@app.put("/operations/platform-tasks/{task_id}", response_model=PlatformTask, dependencies=[Depends(require_api_key)])
def update_platform_task_endpoint(task_id: str, req: PlatformTaskUpdateRequest) -> PlatformTask:
    payload = update_platform_task(
        settings.root_dir,
        task_id=task_id,
        status=req.status,
        owner=req.owner,
        due_date=req.due_date,
        note=req.note,
    )
    return PlatformTask(**payload)


@app.get("/operations/platform-tasks/{task_id}", response_model=PlatformTaskDetailResponse, dependencies=[Depends(require_api_key)])
def get_platform_task_detail(task_id: str, date: str | None = Query(default=None)) -> PlatformTaskDetailResponse:
    payload = get_platform_task(settings.root_dir, task_id=task_id, event_date=date)
    return PlatformTaskDetailResponse(
        task=PlatformTask(**payload["task"]),
        history_path=payload["history_path"],
        history=payload["history"],
    )


@app.post("/operations/platform-tasks/{task_id}/transition", response_model=PlatformTask, dependencies=[Depends(require_api_key)])
def transition_platform_task_endpoint(task_id: str, req: PlatformTaskTransitionRequest) -> PlatformTask:
    payload = transition_platform_task(
        settings.root_dir,
        task_id=task_id,
        target_status=req.target_status,
        owner=req.owner,
        due_date=req.due_date,
        note=req.note,
    )
    return PlatformTask(**payload)


@app.post("/operations/platform-tasks/from-confirmation", response_model=PlatformTask, dependencies=[Depends(require_api_key)])
def create_platform_task_from_confirmation_endpoint(
    confirmation_id: str = Query(...),
    date: str | None = Query(default=None),
    owner: str = Query(default=""),
    due_date: str = Query(default=""),
    created_by: str = Query(default="system"),
    note: str = Query(default=""),
) -> PlatformTask:
    confirmation_payload = list_evolution_confirmations(settings.root_dir, event_date=date, limit=2000)
    confirmation = next(
        (item for item in confirmation_payload["items"] if str(item.get("confirmation_id") or "") == confirmation_id),
        None,
    )
    if confirmation is None:
        raise HTTPException(status_code=404, detail=f"confirmation not found: {confirmation_id}")
    payload = create_platform_task_from_confirmation(
        settings.root_dir,
        confirmation=confirmation,
        owner=owner,
        due_date=due_date,
        created_by=created_by,
        note=note,
        event_date=date,
    )
    return PlatformTask(**payload)


@app.get("/operations/platform-task-report", response_model=PlatformTaskReportResponse, dependencies=[Depends(require_api_key)])
def platform_task_report(
    date: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> PlatformTaskReportResponse:
    payload = build_task_report(settings.root_dir, event_date=date)
    report_path = ""
    if save:
        report_path = str(write_task_report(settings.root_dir, event_date=payload["report_date"]))
    content = "\n".join(
        [
            f"任务总数：{payload['total']}",
            f"任务台账：{payload['task_path']}",
        ]
    )
    return PlatformTaskReportResponse(
        report_path=report_path,
        event_date=payload["report_date"],
        total=payload["total"],
        content=content,
    )


@app.get("/operations/platform-task-history", response_model=PlatformTaskHistoryResponse, dependencies=[Depends(require_api_key)])
def platform_task_history(
    date: str | None = Query(default=None),
) -> PlatformTaskHistoryResponse:
    path = get_task_history_path(settings.root_dir, event_date=date)
    items = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                items.append(item)
    return PlatformTaskHistoryResponse(
        total=len(items),
        event_date=date or "",
        history_path=str(path),
        items=items,
    )


@app.get("/operations/platform-task-history-report", response_model=PlatformTaskHistoryReportResponse, dependencies=[Depends(require_api_key)])
def platform_task_history_report(
    date: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> PlatformTaskHistoryReportResponse:
    payload = build_task_history_report(settings.root_dir, event_date=date)
    report_path = ""
    if save:
        report_path = str(write_task_history_report(settings.root_dir, event_date=payload["report_date"]))
    content = "\n".join(
        [
            f"历史总数：{payload['total']}",
            f"历史路径：{payload['history_path']}",
        ]
    )
    return PlatformTaskHistoryReportResponse(
        report_path=report_path,
        event_date=payload["report_date"],
        total=payload["total"],
        content=content,
    )


@app.get("/operations/platform-task-history-report", response_model=PlatformTaskHistoryReportResponse, dependencies=[Depends(require_api_key)])
def platform_task_history_report(
    date: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> PlatformTaskHistoryReportResponse:
    payload = build_task_history_report(settings.root_dir, event_date=date)
    report_path = ""
    if save:
        report_path = str(write_task_history_report(settings.root_dir, event_date=payload["report_date"]))
    content_lines = [
        f"历史总数：{payload['total']}",
        f"历史路径：{payload['history_path']}",
    ]
    return PlatformTaskHistoryReportResponse(
        report_path=report_path,
        event_date=payload["report_date"],
        total=payload["total"],
        content="\n".join(content_lines),
    )


@app.get("/operations/assets", response_model=AssetManifestResponse, dependencies=[Depends(require_api_key)])
def list_assets(
    knowledge_base_id: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    logical_path: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
) -> AssetManifestResponse:
    payload = list_asset_versions(
        settings.root_dir,
        knowledge_base_id=knowledge_base_id,
        asset_type=asset_type,
        stage=stage,
        logical_path=logical_path,
        limit=limit,
    )
    return AssetManifestResponse(**payload)


@app.get("/operations/version-reconciliation", response_model=VersionReconciliationResponse, dependencies=[Depends(require_api_key)])
def version_reconciliation(
    date: str | None = Query(default=None),
    knowledge_base_id: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> VersionReconciliationResponse:
    payload = build_version_reconciliation(settings.root_dir, event_date=date, knowledge_base_id=knowledge_base_id)
    report_path = ""
    if save:
        report_path = str(
            write_version_reconciliation(
                settings.root_dir,
                event_date=payload["report_date"],
                knowledge_base_id=knowledge_base_id,
            )
        )
    content = "\n".join(
        [
            f"事件总数：{payload['event_total']}",
            f"资产总数：{payload['asset_total']}",
            f"已关联引用：{payload['linked_ref_total']}",
            f"缺失引用：{payload['missing_ref_total']}",
            f"孤儿资产：{payload['orphan_asset_total']}",
        ]
    )
    return VersionReconciliationResponse(
        report_path=report_path,
        report_date=payload["report_date"],
        event_total=payload["event_total"],
        asset_total=payload["asset_total"],
        linked_ref_total=payload["linked_ref_total"],
        missing_ref_total=payload["missing_ref_total"],
        orphan_asset_total=payload["orphan_asset_total"],
        content=content,
    )


@app.get("/operations/replay-report", response_model=ReplayReportResponse, dependencies=[Depends(require_api_key)])
def replay_report(
    date: str | None = Query(default=None),
    knowledge_base_id: str | None = Query(default=None),
    save: bool = Query(default=True),
) -> ReplayReportResponse:
    payload = build_replay_report(settings.root_dir, event_date=date, knowledge_base_id=knowledge_base_id)
    report_path = ""
    if save:
        report_path = str(
            write_replay_report(
                settings.root_dir,
                event_date=payload["report_date"],
                knowledge_base_id=knowledge_base_id,
            )
        )
    return ReplayReportResponse(
        report_path=report_path,
        report_date=payload["report_date"],
        event_total=payload["event_total"],
        asset_total=payload["asset_total"],
        content=payload["summary"],
    )


@app.get("/operations/daily-report/automation", response_model=DailyReportAutomationStatusResponse, dependencies=[Depends(require_api_key)])
def daily_report_automation_status() -> DailyReportAutomationStatusResponse:
    payload = load_daily_report_automation_status(settings.root_dir)
    return DailyReportAutomationStatusResponse(**payload)


@app.post("/operations/daily-report/automation/run", response_model=DailyReportAutomationRunResponse, dependencies=[Depends(require_api_key)])
def daily_report_automation_run(date: str | None = Query(default=None)) -> DailyReportAutomationRunResponse:
    payload = run_daily_report_automation(settings.root_dir, report_date=date, force=bool(date))
    return DailyReportAutomationRunResponse(**payload)


@app.post("/raw-files/pipeline", response_model=RawPipelineResponse, dependencies=[Depends(require_api_key)])
def trigger_raw_pipeline(
    stage: str = Query(default="all"),
    folder: str | None = Query(default=None),
    force: bool = Query(default=False),
) -> RawPipelineResponse:
    status = get_pipeline_status()
    if status.get("running") and not force:
        return RawPipelineResponse(started=False, status=RawPipelineStatus(**status))
    trigger_reason = f"{stage}:{folder or 'all'}"
    started_status = start_pipeline(stage=stage, folder=folder, trigger_reason=trigger_reason, force=force)
    return RawPipelineResponse(started=bool(started_status.get("running")), status=RawPipelineStatus(**started_status))


@app.get("/pipeline-config", response_model=PipelineConfigResponse, dependencies=[Depends(require_api_key)])
def read_pipeline_config() -> PipelineConfigResponse:
    config = load_pipeline_config(settings.root_dir)
    return PipelineConfigResponse(
        config_path=str(get_pipeline_config_path(settings.root_dir)),
        config=config,
        updated_at=str(config.get("updated_at", "")),
    )


@app.put("/pipeline-config", response_model=PipelineConfigResponse, dependencies=[Depends(require_api_key)])
def update_pipeline_config(req: PipelineConfigUpdateRequest) -> PipelineConfigResponse:
    config = save_pipeline_config(settings.root_dir, req.config)
    return PipelineConfigResponse(
        config_path=str(get_pipeline_config_path(settings.root_dir)),
        config=config,
        updated_at=str(config.get("updated_at", "")),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("kb_api.main:app", host=settings.host, port=settings.port, reload=False)
