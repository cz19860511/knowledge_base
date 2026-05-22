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
