from __future__ import annotations

from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    normalize: bool | None = None


class EmbedResponse(BaseModel):
    model: str
    provider: str
    dimension: int
    count: int
    normalized: bool
    embeddings: list[list[float]]


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    device: str
    max_length: int
    normalize: bool
