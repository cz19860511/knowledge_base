from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    normalize: bool | None = None
    input_type: Literal["document", "query"] = "document"
    instruction: str | None = None


class EmbedResponse(BaseModel):
    model: str
    provider: str
    dimension: int
    count: int
    normalized: bool
    input_type: str
    pooling: str
    embeddings: list[list[float]]


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    device: str
    max_length: int
    normalize: bool
    pooling: str
    query_instruction_enabled: bool
