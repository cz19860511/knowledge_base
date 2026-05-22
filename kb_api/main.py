from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException

from .config import settings
from .rag import load_chunks, search
from .schemas import (
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    RetrieveRequest,
    RetrieveResponse,
)


app = FastAPI(title="kb-api", version="0.1.0")


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
    return {
        "status": "ok",
        "knowledge_base_id": settings.knowledge_base_id,
        "batch_id": settings.batch_id,
        "retrieval_mode": settings.retrieval_mode,
    }


@app.get("/knowledge-bases", response_model=KnowledgeBaseListResponse, dependencies=[Depends(require_api_key)])
def list_knowledge_bases() -> KnowledgeBaseListResponse:
    chunks = load_chunks()
    return KnowledgeBaseListResponse(
        total=1,
        knowledge_base_list=[
            KnowledgeBaseItem(
                knowledge_base_id=settings.knowledge_base_id,
                name="AI+智能问答智能体标准库",
                description="本地知识库经由 General 接口适配后供 AgentArts 调用。",
                doc_count=len({row["doc_id"] for row in chunks}),
                chunk_count=len(chunks),
            )
        ],
    )


@app.post("/knowledge-bases/retrieve", response_model=RetrieveResponse, dependencies=[Depends(require_api_key)])
def retrieve(req: RetrieveRequest) -> RetrieveResponse:
    if req.knowledge_base_ids and settings.knowledge_base_id not in req.knowledge_base_ids:
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("kb_api.main:app", host=settings.host, port=settings.port, reload=False)
