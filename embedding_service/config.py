from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    provider: str = os.getenv("KB_EMBEDDING_PROVIDER", "transformers")
    model_path: str = os.getenv("KB_EMBEDDING_MODEL_PATH", "/data/kb/models/bge-small-zh-v1.5")
    model_name: str = os.getenv("KB_EMBEDDING_MODEL_NAME", "bge-small-zh-v1.5")
    device: str = os.getenv("KB_EMBEDDING_DEVICE", "cpu")
    max_length: int = int(os.getenv("KB_EMBEDDING_MAX_LENGTH", "512"))
    batch_size: int = int(os.getenv("KB_EMBEDDING_BATCH_SIZE", "16"))
    normalize: bool = os.getenv("KB_EMBEDDING_NORMALIZE", "true").lower() in {"1", "true", "yes"}
    host: str = os.getenv("KB_EMBEDDING_HOST", "0.0.0.0")
    port: int = int(os.getenv("KB_EMBEDDING_PORT", "9100"))


settings = Settings()
