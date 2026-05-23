from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from .config import settings
from pipeline_config import get_pipeline_config_path, load_pipeline_config


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class MockEmbedder:
    """Deterministic fallback used only for service wiring tests."""

    dimension = 384

    def encode(self, texts: list[str], normalize: bool, input_type: str = "document", instruction: str | None = None) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype="float32")
        for row_idx, text in enumerate(texts):
            tokens = [text[i : i + 2] for i in range(max(len(text) - 1, 1))]
            for token in tokens:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] % 2 else -1.0
                vectors[row_idx, bucket] += sign
        return _normalize(vectors) if normalize else vectors


class TransformersEmbedder:
    def __init__(self, runtime: dict[str, object]) -> None:
        model_path = Path(str(runtime["model_path"]))
        if not model_path.exists():
            raise FileNotFoundError(
                f"Embedding model path does not exist: {model_path}. "
                "Put a local Chinese embedding model there or set KB_EMBEDDING_MODEL_PATH."
            )

        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(model_path), local_files_only=True)
        self.device = str(runtime["device"])
        self.model.to(self.device)
        self.model.eval()
        self.dimension = int(self.model.config.hidden_size)
        self.pooling = str(runtime["pooling"])
        self.batch_size = int(runtime["batch_size"])
        self.max_length = int(runtime["max_length"])
        self.query_instruction = str(runtime["query_instruction"])
        self.normalize_output = bool(runtime["normalize"])

    def _prepare_texts(self, texts: list[str], input_type: str, instruction: str | None) -> list[str]:
        if input_type != "query":
            return texts
        prefix = instruction if instruction is not None else self.query_instruction
        if not prefix:
            return texts
        return [prefix + text for text in texts]

    def _pool(self, hidden, attention_mask):
        pooling = self.pooling.lower()
        if pooling == "cls":
            return hidden[:, 0]
        if pooling == "mean":
            mask = attention_mask.unsqueeze(-1).expand(hidden.size()).float()
            return (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        raise ValueError(f"unsupported pooling mode: {self.pooling}")

    def encode(self, texts: list[str], normalize: bool, input_type: str = "document", instruction: str | None = None) -> np.ndarray:
        vectors: list[np.ndarray] = []
        prepared_texts = self._prepare_texts(texts, input_type=input_type, instruction=instruction)
        with self.torch.no_grad():
            for start in range(0, len(prepared_texts), self.batch_size):
                batch = prepared_texts[start : start + self.batch_size]
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                output = self.model(**encoded)
                pooled = self._pool(output.last_hidden_state, encoded["attention_mask"])
                if normalize:
                    pooled = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
                vectors.append(pooled.cpu().numpy().astype("float32"))
        return np.vstack(vectors)


def _runtime_embedding_config() -> dict[str, object]:
    file_config = load_pipeline_config(settings.root_dir).get("embedding", {})
    if not isinstance(file_config, dict):
        file_config = {}
    path = get_pipeline_config_path(settings.root_dir)
    mtime = path.stat().st_mtime if path.exists() else 0.0
    runtime = {
        "provider": str(file_config.get("provider", settings.provider)),
        "model_path": str(file_config.get("model_path", settings.model_path)),
        "model_name": str(file_config.get("model_name", settings.model_name)),
        "device": str(file_config.get("device", settings.device)),
        "batch_size": int(file_config.get("batch_size", settings.batch_size)),
        "pooling": str(file_config.get("pooling", settings.pooling)),
        "query_instruction": str(file_config.get("query_instruction", settings.query_instruction)),
        "max_length": int(file_config.get("max_length", settings.max_length)),
        "normalize": bool(file_config.get("normalize", settings.normalize)),
        "config_mtime": mtime,
    }
    return runtime


_EMBEDDER_CACHE: dict[str, object] = {"signature": None, "embedder": None}


def get_embedder():
    runtime = _runtime_embedding_config()
    signature = tuple(sorted(runtime.items()))
    if _EMBEDDER_CACHE["signature"] == signature and _EMBEDDER_CACHE["embedder"] is not None:
        return _EMBEDDER_CACHE["embedder"]

    provider = str(runtime["provider"]).lower()
    if provider == "mock":
        embedder = MockEmbedder()
    elif provider == "transformers":
        embedder = TransformersEmbedder(runtime)
    else:
        raise ValueError(f"unsupported embedding provider: {runtime['provider']}")

    _EMBEDDER_CACHE["signature"] = signature
    _EMBEDDER_CACHE["embedder"] = embedder
    return embedder
