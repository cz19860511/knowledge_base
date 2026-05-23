from __future__ import annotations

from fastapi import FastAPI

from .config import settings
from .model import get_embedder
from .schemas import EmbedRequest, EmbedResponse, HealthResponse


app = FastAPI(title="embedding-service", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider=settings.provider,
        model=settings.model_name,
        device=settings.device,
        max_length=settings.max_length,
        normalize=settings.normalize,
        pooling=settings.pooling,
        query_instruction_enabled=bool(settings.query_instruction),
    )


@app.get("/models")
def models() -> dict:
    return {
        "active": {
            "provider": settings.provider,
            "model_name": settings.model_name,
            "model_path": settings.model_path,
            "device": settings.device,
            "max_length": settings.max_length,
            "batch_size": settings.batch_size,
            "pooling": settings.pooling,
            "query_instruction_enabled": bool(settings.query_instruction),
        }
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    embedder = get_embedder()
    normalize = settings.normalize if req.normalize is None else req.normalize
    vectors = embedder.encode(req.texts, normalize=normalize, input_type=req.input_type, instruction=req.instruction)
    return EmbedResponse(
        model=settings.model_name,
        provider=settings.provider,
        dimension=int(vectors.shape[1]),
        count=int(vectors.shape[0]),
        normalized=normalize,
        input_type=req.input_type,
        pooling=settings.pooling,
        embeddings=vectors.tolist(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("embedding_service.main:app", host=settings.host, port=settings.port, reload=False)
