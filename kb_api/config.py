from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path = Path(os.getenv("KB_ROOT_DIR", "/data/kb"))
    batch_id: str = os.getenv("KB_BATCH_ID", "batch_20260521")
    knowledge_base_id: str = os.getenv("KB_KB_ID", "ai_qna_standard_v1")
    api_key: str = os.getenv("KB_API_KEY", "change-me")
    embedding_model_name: str = os.getenv("KB_EMBEDDING_MODEL_NAME", "bge-small-zh-v1.5")
    host: str = os.getenv("KB_HOST", "0.0.0.0")
    port: int = int(os.getenv("KB_PORT", "8080"))
    top_k_default: int = int(os.getenv("KB_TOP_K_DEFAULT", "5"))
    search_threshold: float = float(os.getenv("KB_SEARCH_THRESHOLD", "0.12"))
    retrieval_mode: str = os.getenv("KB_RETRIEVAL_MODE", "hybrid")
    keyword_weight: float = float(os.getenv("KB_KEYWORD_WEIGHT", "0.60"))
    embedding_weight: float = float(os.getenv("KB_EMBEDDING_WEIGHT", "0.40"))
    rule_weight: float = float(os.getenv("KB_RULE_WEIGHT", "0.20"))
    query_expansion_enabled: bool = os.getenv("KB_QUERY_EXPANSION_ENABLED", "true").lower() in {"1", "true", "yes"}
    candidate_multiplier: int = int(os.getenv("KB_CANDIDATE_MULTIPLIER", "8"))
    embedding_service_url: str = os.getenv("KB_EMBEDDING_SERVICE_URL", "http://embedding-service:9100")
    embedding_service_timeout: int = int(os.getenv("KB_EMBEDDING_SERVICE_TIMEOUT", "30"))

    @property
    def chunks_jsonl(self) -> Path:
        return self.root_dir / "chunks" / self.batch_id / "chunks.jsonl"

    @property
    def raw_source_root(self) -> Path:
        return self.root_dir / "raw" / "标准化体系_分类版"

    @property
    def operations_dir(self) -> Path:
        return self.root_dir / "operations"

    @property
    def raw_manifest_path(self) -> Path:
        return self.operations_dir / "raw_manifest.json"

    @property
    def raw_pipeline_status_path(self) -> Path:
        return self.operations_dir / "raw_pipeline_status.json"

    @property
    def raw_pipeline_log_path(self) -> Path:
        return self.operations_dir / "raw_pipeline.log"

    @property
    def vector_db(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "vector_index.sqlite"

    @property
    def vectorizer_path(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "vectorizer.joblib"

    @property
    def vector_matrix_path(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "vector_matrix.npz"

    @property
    def keyword_vectorizer_path(self) -> Path:
        path = self.root_dir / "vectors" / self.batch_id / "keyword_vectorizer.joblib"
        return path if path.exists() else self.vectorizer_path

    @property
    def keyword_matrix_path(self) -> Path:
        path = self.root_dir / "vectors" / self.batch_id / "keyword_matrix.npz"
        return path if path.exists() else self.vector_matrix_path

    @property
    def embedding_matrix_path(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "embedding_matrix.npy"

    @property
    def embedding_model_path(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "embedding_model.joblib"

    @property
    def manifest_path(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "vector_manifest.json"

    @property
    def hybrid_manifest_path(self) -> Path:
        return self.root_dir / "vectors" / self.batch_id / "hybrid_manifest.json"


settings = Settings()
