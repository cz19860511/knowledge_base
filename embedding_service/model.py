from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import settings


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class MockEmbedder:
    """Deterministic fallback used only for service wiring tests."""

    dimension = 384

    def encode(self, texts: list[str], normalize: bool) -> np.ndarray:
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
    def __init__(self) -> None:
        model_path = Path(settings.model_path)
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
        self.model.to(settings.device)
        self.model.eval()
        self.dimension = int(self.model.config.hidden_size)

    def encode(self, texts: list[str], normalize: bool) -> np.ndarray:
        vectors: list[np.ndarray] = []
        with self.torch.no_grad():
            for start in range(0, len(texts), settings.batch_size):
                batch = texts[start : start + settings.batch_size]
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=settings.max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(settings.device) for key, value in encoded.items()}
                output = self.model(**encoded)
                hidden = output.last_hidden_state
                mask = encoded["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
                if normalize:
                    pooled = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
                vectors.append(pooled.cpu().numpy().astype("float32"))
        return np.vstack(vectors)


@lru_cache(maxsize=1)
def get_embedder():
    provider = settings.provider.lower()
    if provider == "mock":
        return MockEmbedder()
    if provider == "transformers":
        return TransformersEmbedder()
    raise ValueError(f"unsupported embedding provider: {settings.provider}")
