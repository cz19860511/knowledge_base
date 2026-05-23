from __future__ import annotations

from fastapi import FastAPI

from .config import settings
from .model import get_embedder, _runtime_embedding_config
from .schemas import EmbedRequest, EmbedResponse, HealthResponse


app = FastAPI(title="embedding-service", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    runtime = _runtime_embedding_config()
    return HealthResponse(
        status="ok",
        provider=str(runtime["provider"]),
        model=str(runtime["model_name"]),
        device=str(runtime["device"]),
        max_length=int(runtime["max_length"]),
        normalize=bool(runtime["normalize"]),
        pooling=str(runtime["pooling"]),
        query_instruction_enabled=bool(runtime["query_instruction"]),
    )


@app.get("/models")
def models() -> dict:
    runtime = _runtime_embedding_config()
    return {
        "active": {
            "provider": str(runtime["provider"]),
            "model_name": str(runtime["model_name"]),
            "model_path": str(runtime["model_path"]),
            "device": str(runtime["device"]),
            "max_length": int(runtime["max_length"]),
            "batch_size": int(runtime["batch_size"]),
            "pooling": str(runtime["pooling"]),
            "query_instruction_enabled": bool(runtime["query_instruction"]),
        }
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    runtime = _runtime_embedding_config()
    embedder = get_embedder()
    normalize = bool(runtime["normalize"]) if req.normalize is None else req.normalize
    vectors = embedder.encode(req.texts, normalize=normalize, input_type=req.input_type, instruction=req.instruction)
    return EmbedResponse(
        model=str(runtime["model_name"]),
        provider=str(runtime["provider"]),
        dimension=int(vectors.shape[1]),
        count=int(vectors.shape[0]),
        normalized=normalize,
        input_type=req.input_type,
        pooling=str(runtime["pooling"]),
        embeddings=vectors.tolist(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("embedding_service.main:app", host=settings.host, port=settings.port, reload=False)
