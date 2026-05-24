from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .rag import load_chunks, search
from .raw_store import delete_raw_file, get_pipeline_status, list_raw_files, rollback_raw_file, save_uploaded_files, start_pipeline
from .schemas import (
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseRegistryResponse,
    KnowledgeBaseRegistryUpsertRequest,
    RawDeleteResponse,
    RawFileListResponse,
    RawPipelineResponse,
    RawPipelineStatus,
    RawUploadResponse,
    RawRollbackResponse,
    PipelineConfigResponse,
    PipelineConfigUpdateRequest,
    RetrieveRequest,
    RetrieveResponse,
)
from knowledge_base_registry import delete_registry_item, get_active_registry_item, get_registry_path, load_registry, set_active_registry_item, upsert_registry_item
from knowledge_base_paths import ensure_knowledge_base_workspace
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
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.put("/knowledge-base-registry/{knowledge_base_id}", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def update_knowledge_base_registry(knowledge_base_id: str, req: KnowledgeBaseRegistryUpsertRequest) -> KnowledgeBaseRegistryResponse:
    payload = req.model_dump()
    payload["knowledge_base_id"] = knowledge_base_id
    registry = upsert_registry_item(settings.root_dir, payload)
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.delete("/knowledge-base-registry/{knowledge_base_id}", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def delete_knowledge_base_registry(knowledge_base_id: str) -> KnowledgeBaseRegistryResponse:
    registry = delete_registry_item(settings.root_dir, knowledge_base_id)
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.post("/knowledge-base-registry/{knowledge_base_id}/activate", response_model=KnowledgeBaseRegistryResponse, dependencies=[Depends(require_api_key)])
def activate_knowledge_base_registry(knowledge_base_id: str) -> KnowledgeBaseRegistryResponse:
    registry = set_active_registry_item(settings.root_dir, knowledge_base_id)
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
    return KnowledgeBaseRegistryResponse(
        **registry,
        registry_path=str(get_registry_path(settings.root_dir)),
    )


@app.post("/knowledge-bases/retrieve", response_model=RetrieveResponse, dependencies=[Depends(require_api_key)])
def retrieve(req: RetrieveRequest) -> RetrieveResponse:
    active_kb_id = get_active_registry_item(settings.root_dir).get("knowledge_base_id", settings.knowledge_base_id)
    if req.knowledge_base_ids and active_kb_id not in req.knowledge_base_ids:
        return RetrieveResponse(total=0, search_result_list=[])
    top_k = req.top_k or settings.top_k_default
    threshold = req.search_threshold if req.search_threshold is not None else settings.search_threshold
    hits = search(req.query, top_k=top_k, threshold=threshold)
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
