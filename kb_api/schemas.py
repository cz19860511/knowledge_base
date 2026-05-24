from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeBaseItem(BaseModel):
    knowledge_base_id: str
    name: str
    description: str | None = None
    doc_count: int = 0
    chunk_count: int = 0


class KnowledgeBaseListResponse(BaseModel):
    total: int
    knowledge_base_list: list[KnowledgeBaseItem]


class KnowledgeBaseRegistryItem(BaseModel):
    knowledge_base_id: str
    name: str
    description: str | None = None
    owner: str | None = None
    status: str = "active"
    root_dir: str | None = None
    default_batch_id: str | None = None
    doc_count: int = 0
    chunk_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class KnowledgeBaseRegistryResponse(BaseModel):
    version: int = 1
    active_knowledge_base_id: str = ""
    items: list[KnowledgeBaseRegistryItem]
    registry_path: str = ""
    updated_at: str = ""


class KnowledgeBaseRegistryUpsertRequest(BaseModel):
    knowledge_base_id: str
    name: str
    description: str | None = None
    owner: str | None = None
    status: str = "active"
    root_dir: str | None = None
    default_batch_id: str | None = None
    doc_count: int = 0
    chunk_count: int = 0


class RetrieveExtraParam(BaseModel):
    key: str
    value: str


class RetrieveRequest(BaseModel):
    knowledge_base_ids: list[str] = Field(default_factory=list)
    query: str
    method: Literal["doc"] = "doc"
    offset: int = 0
    limit: int = 5
    top_k: int = 5
    search_threshold: float | None = None
    extra_params: list[RetrieveExtraParam] = Field(default_factory=list)


class RetrieveHit(BaseModel):
    knowledge_base_id: str
    file_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    keyword_score: float | None = None
    embedding_score: float | None = None
    rule_score: float | None = None
    matched_rules: list[str] | None = None
    retrieval_mode: str | None = None
    doc_type: str | None = None
    folder: str | None = None
    version: str | None = None
    section_path: str | None = None
    source_file: str | None = None
    selected_md: str | None = None


class RetrieveResponse(BaseModel):
    total: int
    search_result_list: list[RetrieveHit]


class RawFileVersion(BaseModel):
    version: str
    uploaded_at: str
    size_bytes: int = 0
    checksum: str | None = None
    stored_path: str | None = None
    source_version: str | None = None
    restored_from: str | None = None


class RawFileItem(BaseModel):
    raw_key: str
    folder: str
    file_name: str
    relative_path: str
    file_path: str
    exists: bool = True
    deleted: bool = False
    version: str = "v1"
    version_count: int = 1
    upload_time: str = ""
    updated_at: str = ""
    size_bytes: int = 0
    checksum: str | None = None
    history: list[RawFileVersion] = Field(default_factory=list)


class RawFileListResponse(BaseModel):
    total: int
    allowed_folders: list[str]
    raw_file_list: list[RawFileItem]


class RawUploadItem(BaseModel):
    action: str
    item: RawFileItem


class RawUploadResponse(BaseModel):
    uploaded_count: int
    created_count: int
    updated_count: int
    items: list[RawFileItem]
    pipeline_started: bool = False
    pipeline_status: dict | None = None


class RawDeleteResponse(BaseModel):
    deleted: bool
    item: RawFileItem


class RawRollbackResponse(BaseModel):
    restored: bool
    restored_from_version: str
    item: RawFileItem


class RawPipelineStatus(BaseModel):
    running: bool = False
    state: str = "idle"
    current_stage: str = ""
    current_step: str = ""
    current_folder: str = ""
    run_id: str = ""
    trigger_reason: str = ""
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    last_success_at: str = ""
    last_error: str = ""
    exit_code: int | None = None


class RawPipelineResponse(BaseModel):
    started: bool = False
    status: RawPipelineStatus


class PipelineConfigResponse(BaseModel):
    config_path: str
    config: dict
    updated_at: str = ""


class PipelineConfigUpdateRequest(BaseModel):
    config: dict
