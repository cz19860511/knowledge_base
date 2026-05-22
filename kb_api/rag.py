from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from functools import lru_cache

import joblib
import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize

from .config import settings


@lru_cache(maxsize=1)
def load_chunks() -> list[dict]:
    rows: list[dict] = []
    with settings.chunks_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@lru_cache(maxsize=1)
def load_vectorizer():
    return joblib.load(settings.keyword_vectorizer_path)


@lru_cache(maxsize=1)
def load_matrix():
    return sparse.load_npz(settings.keyword_matrix_path)


@lru_cache(maxsize=1)
def load_embedding_matrix():
    if not settings.embedding_matrix_path.exists():
        return None
    return np.load(settings.embedding_matrix_path)


@lru_cache(maxsize=1)
def load_embedding_model():
    if not settings.embedding_model_path.exists():
        return None
    return joblib.load(settings.embedding_model_path)


def load_metadata(chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    conn = sqlite3.connect(settings.vector_db)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in chunk_ids)
    query = f"""
        SELECT chunk_id, doc_id, folder, doc_type, version, parser,
               chunk_index, chunk_count, char_count, section_path, source_file,
               selected_md, text
        FROM chunks
        WHERE chunk_id IN ({placeholders})
    """
    rows = cur.execute(query, chunk_ids).fetchall()
    conn.close()
    return {
        row[0]: {
            "chunk_id": row[0],
            "doc_id": row[1],
            "folder": row[2],
            "doc_type": row[3],
            "version": row[4],
            "parser": row[5],
            "chunk_index": row[6],
            "chunk_count": row[7],
            "char_count": row[8],
            "section_path": row[9],
            "source_file": row[10],
            "selected_md": row[11],
            "text": row[12],
        }
        for row in rows
    }


def _safe_normalize_scores(scores: np.ndarray) -> np.ndarray:
    positive = np.maximum(scores.astype("float64"), 0.0)
    max_score = float(positive.max()) if positive.size else 0.0
    if max_score <= 0:
        return positive
    return positive / max_score


def _service_query_embedding(query: str):
    endpoint = settings.embedding_service_url.rstrip("/") + "/embed"
    payload = json.dumps({"texts": [query], "normalize": True}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=settings.embedding_service_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    embeddings = data.get("embeddings") or []
    if not embeddings:
        return None
    return normalize(np.asarray(embeddings[:1], dtype="float32"), norm="l2").astype("float32")


def _query_embedding(query: str, q_vec):
    embedding_model = load_embedding_model()
    if not embedding_model:
        return None

    provider = embedding_model.get("provider") if isinstance(embedding_model, dict) else None
    if provider == "lsa":
        if "components" in embedding_model:
            dense = q_vec @ embedding_model["components"].T
        else:
            dense = embedding_model["model"].transform(q_vec)
        return normalize(dense, norm="l2").astype("float32")
    if provider == "service":
        return _service_query_embedding(query)

    return None


def _hybrid_scores(keyword_scores: np.ndarray, embedding_scores: np.ndarray | None) -> tuple[np.ndarray, str]:
    mode = settings.retrieval_mode.lower()
    keyword_norm = _safe_normalize_scores(keyword_scores)

    if embedding_scores is None:
        return keyword_norm, "keyword"

    embedding_norm = _safe_normalize_scores(embedding_scores)
    if mode == "keyword":
        return keyword_norm, "keyword"
    if mode == "embedding":
        return embedding_norm, "embedding"

    keyword_weight = max(settings.keyword_weight, 0.0)
    embedding_weight = max(settings.embedding_weight, 0.0)
    weight_sum = keyword_weight + embedding_weight
    if weight_sum <= 0:
        keyword_weight, embedding_weight, weight_sum = 0.45, 0.55, 1.0

    final_scores = (keyword_weight / weight_sum) * keyword_norm + (embedding_weight / weight_sum) * embedding_norm
    return final_scores, "hybrid"


def search(query: str, top_k: int, threshold: float) -> list[dict]:
    vectorizer = load_vectorizer()
    matrix = load_matrix()
    chunks = load_chunks()

    q_vec = vectorizer.transform([query])
    keyword_scores = (matrix @ q_vec.T).toarray().ravel()

    embedding_scores = None
    embedding_matrix = load_embedding_matrix()
    q_embedding = _query_embedding(query, q_vec)
    if (
        embedding_matrix is not None
        and q_embedding is not None
        and embedding_matrix.shape[1] == q_embedding.shape[1]
    ):
        embedding_scores = (embedding_matrix @ q_embedding.ravel()).ravel()

    scores, retrieval_mode = _hybrid_scores(keyword_scores, embedding_scores)
    candidate_count = max(top_k, min(len(chunks), top_k * max(settings.candidate_multiplier, 1)))
    top_idx = scores.argsort()[::-1][:candidate_count]

    result: list[dict] = []
    metadata = load_metadata([chunks[i]["chunk_id"] for i in top_idx])
    for idx in top_idx:
        score = float(scores[idx])
        if score < threshold:
            continue
        row = chunks[idx]
        meta = metadata.get(row["chunk_id"], {})
        result.append(
            {
                "knowledge_base_id": settings.knowledge_base_id,
                "file_id": row["doc_id"],
                "chunk_id": row["chunk_id"],
                "title": f"{row.get('doc_type', '')} / {row.get('folder', '')} / {row.get('section_path', '')}".strip(" /"),
                "content": row["text"],
                "score": score,
                "keyword_score": float(keyword_scores[idx]),
                "embedding_score": float(embedding_scores[idx]) if embedding_scores is not None else None,
                "retrieval_mode": retrieval_mode,
                "doc_type": row.get("doc_type"),
                "folder": row.get("folder"),
                "version": row.get("version"),
                "section_path": row.get("section_path"),
                "source_file": meta.get("source_file", row.get("source_file")),
                "selected_md": meta.get("selected_md", row.get("selected_md")),
            }
        )
        if len(result) >= top_k:
            break
    return result
