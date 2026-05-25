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
    knowledge_base_id: str | None = Field(
        default=None,
        description="优先检索的知识库 ID；未填时回退到 knowledge_base_ids 或当前激活知识库。",
    )
    knowledge_base_ids: list[str] = Field(default_factory=list)
    query: str = Field(min_length=1, max_length=4000)
    method: Literal["doc"] = "doc"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=5, ge=1, le=50)
    top_k: int = Field(default=5, ge=1, le=50)
    search_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
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


class OperationEvent(BaseModel):
    event_id: str
    event_type: str
    knowledge_base_id: str = ""
    source: str = "api"
    actor: str = "system"
    input_assets: list[dict] = Field(default_factory=list)
    output_assets: list[dict] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    status: str = "success"
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int | None = None
    error_message: str = ""
    log_path: str = ""
    remark: str = ""
    created_at: str = ""


class OperationEventListResponse(BaseModel):
    total: int
    event_date: str = ""
    items: list[OperationEvent]


class DailyReportResponse(BaseModel):
    report_path: str = ""
    event_date: str = ""
    total: int = 0
    content: str = ""


class DailyReportIngestResponse(BaseModel):
    knowledge_base_id: str = ""
    root_dir: str = ""
    report_path: str = ""
    selected_md_path: str = ""
    chunks_path: str = ""
    vectors_root: str = ""
    chunk_count: int = 0
    doc_count: int = 0
    report_date: str = ""
    vector_manifest: str = ""
    summary: str = ""
    sqlite: str = ""
    embedding_dim: int = 0


class DailyReportAutomationStatusResponse(BaseModel):
    running: bool = False
    thread_started: bool = False
    scheduled_time: str = "00:10"
    check_interval_seconds: int = 60
    timezone: str = "Asia/Shanghai"
    last_checked_at: str = ""
    last_attempted_date: str = ""
    last_success_date: str = ""
    last_success_at: str = ""
    last_error: str = ""
    last_run_started_at: str = ""
    last_run_finished_at: str = ""
    pending_dates: list[str] = Field(default_factory=list)
    next_planned_date: str = ""


class DailyReportAutomationRunResponse(BaseModel):
    running: bool = False
    scheduled_time: str = "00:10"
    pending_dates: list[str] = Field(default_factory=list)
    results: list[dict] = Field(default_factory=list)
    last_success_date: str = ""
    last_success_at: str = ""
    last_error: str = ""
    last_checked_at: str = ""


class EvolutionSuggestion(BaseModel):
    suggestion_id: str
    category: str
    title: str
    summary: str
    recommendation: str
    evidence: list[str] = Field(default_factory=list)
    scope: str = ""
    risk_level: str = "medium"
    priority: int = 3
    requires_human_confirmation: bool = True
    related_event_types: list[str] = Field(default_factory=list)
    related_knowledge_base_ids: list[str] = Field(default_factory=list)


class EvolutionSuggestionResponse(BaseModel):
    report_date: str = ""
    total_events: int = 0
    total_suggestions: int = 0
    summary: str = ""
    report_path: str = ""
    suggestions: list[EvolutionSuggestion] = Field(default_factory=list)


class EvolutionReportResponse(BaseModel):
    report_path: str = ""
    event_date: str = ""
    total_events: int = 0
    total_suggestions: int = 0
    content: str = ""


class EvolutionTemplateItem(BaseModel):
    template_id: str
    category: str
    title: str
    when_to_use: str
    required_inputs: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    prompt_template: str


class EvolutionTemplatesResponse(BaseModel):
    generated_at: str = ""
    template_pack_id: str = ""
    templates: list[EvolutionTemplateItem] = Field(default_factory=list)


class EvolutionConfirmationSuggestion(BaseModel):
    suggestion_id: str = ""
    category: str = ""
    title: str = ""
    summary: str = ""
    recommendation: str = ""
    evidence: list[str] = Field(default_factory=list)
    scope: str = ""
    risk_level: str = "medium"
    priority: int = 3
    requires_human_confirmation: bool = True
    related_event_types: list[str] = Field(default_factory=list)
    related_knowledge_base_ids: list[str] = Field(default_factory=list)


class EvolutionConfirmationCreateRequest(BaseModel):
    decision: str
    decided_by: str
    note: str = ""
    source_report_date: str = ""
    source_report_path: str = ""
    suggestion: EvolutionConfirmationSuggestion


class EvolutionConfirmationRecord(BaseModel):
    confirmation_id: str = ""
    decision: str = ""
    decided_by: str = ""
    decided_at: str = ""
    note: str = ""
    source_report_date: str = ""
    source_report_path: str = ""
    suggestion: EvolutionConfirmationSuggestion = Field(default_factory=EvolutionConfirmationSuggestion)


class EvolutionConfirmationListResponse(BaseModel):
    total: int = 0
    event_date: str = ""
    confirmation_path: str = ""
    items: list[EvolutionConfirmationRecord] = Field(default_factory=list)


class EvolutionConfirmationReportResponse(BaseModel):
    report_path: str = ""
    event_date: str = ""
    total: int = 0
    content: str = ""


class PlatformTask(BaseModel):
    task_id: str = ""
    title: str = ""
    summary: str = ""
    priority: int = 3
    status: str = "pending"
    owner: str = ""
    due_date: str = ""
    source_type: str = "manual"
    source_id: str = ""
    source_report_date: str = ""
    source_report_path: str = ""
    source_payload: dict = Field(default_factory=dict)
    created_by: str = "system"
    created_at: str = ""
    updated_at: str = ""
    note: str = ""


class PlatformTaskCreateRequest(BaseModel):
    title: str
    summary: str
    priority: int = 3
    status: str = "pending"
    owner: str = ""
    due_date: str = ""
    source_type: str = "manual"
    source_id: str = ""
    source_report_date: str = ""
    source_report_path: str = ""
    source_payload: dict = Field(default_factory=dict)
    created_by: str = "system"
    note: str = ""


class PlatformTaskUpdateRequest(BaseModel):
    status: str | None = None
    owner: str | None = None
    due_date: str | None = None
    note: str | None = None


class PlatformTaskTransitionRequest(BaseModel):
    target_status: str
    owner: str | None = None
    due_date: str | None = None
    note: str | None = None


class PlatformTaskListResponse(BaseModel):
    total: int = 0
    event_date: str = ""
    task_path: str = ""
    items: list[PlatformTask] = Field(default_factory=list)


class PlatformTaskDetailResponse(BaseModel):
    task: PlatformTask = Field(default_factory=PlatformTask)
    history_path: str = ""
    history: list[dict] = Field(default_factory=list)


class PlatformTaskHistoryResponse(BaseModel):
    total: int = 0
    event_date: str = ""
    history_path: str = ""
    items: list[dict] = Field(default_factory=list)


class PlatformTaskReportResponse(BaseModel):
    report_path: str = ""
    event_date: str = ""
    total: int = 0
    content: str = ""


class PlatformTaskHistoryReportResponse(BaseModel):
    report_path: str = ""
    event_date: str = ""
    total: int = 0
    content: str = ""


class AssetRecord(BaseModel):
    asset_id: str
    knowledge_base_id: str
    asset_type: str
    stage: str
    logical_path: str
    version: str
    status: str = "active"
    file_path: str = ""
    checksum: str = ""
    size_bytes: int = 0
    created_by: str = "system"
    created_at: str = ""
    operation_id: str = ""
    parent_asset_id: str = ""
    source_asset_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AssetManifestResponse(BaseModel):
    total: int
    manifest_path: str = ""
    items: list[AssetRecord] = Field(default_factory=list)


class VersionReconciliationResponse(BaseModel):
    report_path: str = ""
    report_date: str = ""
    event_total: int = 0
    asset_total: int = 0
    linked_ref_total: int = 0
    missing_ref_total: int = 0
    orphan_asset_total: int = 0
    content: str = ""


class ReplayReportResponse(BaseModel):
    report_path: str = ""
    report_date: str = ""
    event_total: int = 0
    asset_total: int = 0
    content: str = ""


class PipelineConfigResponse(BaseModel):
    config_path: str
    config: dict
    updated_at: str = ""


class PipelineConfigUpdateRequest(BaseModel):
    config: dict
