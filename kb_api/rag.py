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
from .retrieval_rules import RetrievalRule, expanded_query, match_rules
from knowledge_base_paths import get_active_knowledge_base_id, get_knowledge_base_root


def _resolve_knowledge_base_id(knowledge_base_id: str | None = None) -> str:
    if knowledge_base_id:
        return knowledge_base_id
    return get_active_knowledge_base_id(settings.root_dir)


@lru_cache(maxsize=8)
def _load_chunks_for(knowledge_base_id: str) -> list[dict]:
    rows: list[dict] = []
    chunks_path = get_knowledge_base_root(settings.root_dir, knowledge_base_id) / "chunks" / settings.batch_id / "chunks.jsonl"
    if not chunks_path.exists():
        return rows
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_chunks(knowledge_base_id: str | None = None) -> list[dict]:
    return _load_chunks_for(_resolve_knowledge_base_id(knowledge_base_id))


@lru_cache(maxsize=8)
def _load_vectorizer_for(knowledge_base_id: str):
    base = get_knowledge_base_root(settings.root_dir, knowledge_base_id)
    path = base / "vectors" / settings.batch_id / "keyword_vectorizer.joblib"
    if not path.exists():
        path = base / "vectors" / settings.batch_id / "vectorizer.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def load_vectorizer(knowledge_base_id: str | None = None):
    return _load_vectorizer_for(_resolve_knowledge_base_id(knowledge_base_id))


@lru_cache(maxsize=8)
def _load_matrix_for(knowledge_base_id: str):
    base = get_knowledge_base_root(settings.root_dir, knowledge_base_id)
    path = base / "vectors" / settings.batch_id / "keyword_matrix.npz"
    if not path.exists():
        path = base / "vectors" / settings.batch_id / "vector_matrix.npz"
    if not path.exists():
        return sparse.csr_matrix((0, 0))
    return sparse.load_npz(path)


def load_matrix(knowledge_base_id: str | None = None):
    return _load_matrix_for(_resolve_knowledge_base_id(knowledge_base_id))


@lru_cache(maxsize=8)
def _load_embedding_matrix_for(knowledge_base_id: str):
    path = get_knowledge_base_root(settings.root_dir, knowledge_base_id) / "vectors" / settings.batch_id / "embedding_matrix.npy"
    if not path.exists():
        return None
    return np.load(path)


def load_embedding_matrix(knowledge_base_id: str | None = None):
    return _load_embedding_matrix_for(_resolve_knowledge_base_id(knowledge_base_id))


@lru_cache(maxsize=8)
def _load_embedding_model_for(knowledge_base_id: str):
    path = get_knowledge_base_root(settings.root_dir, knowledge_base_id) / "vectors" / settings.batch_id / "embedding_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def load_embedding_model(knowledge_base_id: str | None = None):
    return _load_embedding_model_for(_resolve_knowledge_base_id(knowledge_base_id))


def load_metadata(chunk_ids: list[str], knowledge_base_id: str | None = None) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    kb_id = _resolve_knowledge_base_id(knowledge_base_id)
    vector_db = get_knowledge_base_root(settings.root_dir, kb_id) / "vectors" / settings.batch_id / "vector_index.sqlite"
    if not vector_db.exists():
        return {}
    conn = sqlite3.connect(vector_db)
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


def _chunk_search_text(row: dict) -> str:
    return "\n".join(
        str(row.get(key) or "")
        for key in ("doc_type", "folder", "section_path", "section_path_end", "source_file", "text")
    )


def _rule_scores(query: str, chunks: list[dict]) -> tuple[np.ndarray, list[str]]:
    if not settings.query_expansion_enabled:
        return np.zeros(len(chunks), dtype="float64"), []

    rules = match_rules(query)
    if not rules:
        return np.zeros(len(chunks), dtype="float64"), []

    scores = np.zeros(len(chunks), dtype="float64")
    for idx, row in enumerate(chunks):
        text = _chunk_search_text(row)
        score = 0.0
        for rule in rules:
            score += _single_rule_score(rule, row, text)
        scores[idx] = max(score, 0.0)
    return scores, [rule.name for rule in rules]


def _single_rule_score(rule: RetrievalRule, row: dict, text: str) -> float:
    score = 0.0
    section = str(row.get("section_path") or "")
    doc_type = str(row.get("doc_type") or "")
    folder = str(row.get("folder") or "")

    for term in rule.boost_terms:
        if term in text:
            score += 1.0
        if term in section:
            score += 0.8

    if doc_type and any(term in doc_type for term in rule.preferred_doc_types):
        score += 0.8
    if folder and any(term in folder for term in rule.preferred_folders):
        score += 0.5

    for term in rule.penalty_terms:
        if term in text:
            score -= 1.2

    return score


def _service_query_embedding(query: str):
    endpoint = settings.embedding_service_url.rstrip("/") + "/embed"
    payload = json.dumps(
        {"texts": [query], "normalize": True, "input_type": "query"},
        ensure_ascii=False,
    ).encode("utf-8")
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


def _query_embedding(query: str, q_vec, knowledge_base_id: str | None = None):
    embedding_model = load_embedding_model(knowledge_base_id)
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


def _hybrid_scores(
    keyword_scores: np.ndarray,
    embedding_scores: np.ndarray | None,
    rule_scores: np.ndarray,
) -> tuple[np.ndarray, str]:
    mode = settings.retrieval_mode.lower()
    keyword_norm = _safe_normalize_scores(keyword_scores)
    rule_norm = _safe_normalize_scores(rule_scores)
    has_rule = bool(rule_norm.size and rule_norm.max() > 0)

    if embedding_scores is None:
        if mode == "keyword" or not has_rule:
            return keyword_norm, "keyword"
        keyword_weight = max(settings.keyword_weight, 0.0)
        rule_weight = max(settings.rule_weight, 0.0)
        weight_sum = keyword_weight + rule_weight
        if weight_sum <= 0:
            return keyword_norm, "keyword"
        return (keyword_weight / weight_sum) * keyword_norm + (rule_weight / weight_sum) * rule_norm, "keyword+rules"

    embedding_norm = _safe_normalize_scores(embedding_scores)
    if mode == "keyword":
        return keyword_norm, "keyword"
    if mode == "embedding":
        return embedding_norm, "embedding"

    keyword_weight = max(settings.keyword_weight, 0.0)
    embedding_weight = max(settings.embedding_weight, 0.0)
    rule_weight = max(settings.rule_weight, 0.0) if has_rule else 0.0
    weight_sum = keyword_weight + embedding_weight + rule_weight
    if weight_sum <= 0:
        keyword_weight, embedding_weight, rule_weight, weight_sum = 0.50, 0.35, 0.15, 1.0

    final_scores = (
        (keyword_weight / weight_sum) * keyword_norm
        + (embedding_weight / weight_sum) * embedding_norm
        + (rule_weight / weight_sum) * rule_norm
    )
    return final_scores, "hybrid"


def search(query: str, top_k: int, threshold: float, knowledge_base_id: str | None = None) -> list[dict]:
    kb_id = _resolve_knowledge_base_id(knowledge_base_id)
    vectorizer = load_vectorizer(kb_id)
    matrix = load_matrix(kb_id)
    chunks = load_chunks(kb_id)
    if not chunks or vectorizer is None or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        return []

    rules = match_rules(query) if settings.query_expansion_enabled else []
    keyword_query = expanded_query(query, rules) if settings.query_expansion_enabled else query
    q_vec = vectorizer.transform([keyword_query])
    keyword_scores = (matrix @ q_vec.T).toarray().ravel()
    rule_scores, matched_rules = _rule_scores(query, chunks)

    embedding_scores = None
    embedding_matrix = load_embedding_matrix(kb_id)
    q_embedding = _query_embedding(query, q_vec, kb_id)
    if (
        embedding_matrix is not None
        and q_embedding is not None
        and embedding_matrix.shape[1] == q_embedding.shape[1]
    ):
        embedding_scores = (embedding_matrix @ q_embedding.ravel()).ravel()

    scores, retrieval_mode = _hybrid_scores(keyword_scores, embedding_scores, rule_scores)
    candidate_count = max(top_k, min(len(chunks), top_k * max(settings.candidate_multiplier, 1)))
    top_idx = scores.argsort()[::-1][:candidate_count]

    result: list[dict] = []
    metadata = load_metadata([chunks[i]["chunk_id"] for i in top_idx], kb_id)
    for idx in top_idx:
        score = float(scores[idx])
        if score < threshold:
            continue
        row = chunks[idx]
        meta = metadata.get(row["chunk_id"], {})
        result.append(
            {
                "knowledge_base_id": kb_id,
                "file_id": row["doc_id"],
                "chunk_id": row["chunk_id"],
                "title": f"{row.get('doc_type', '')} / {row.get('folder', '')} / {row.get('section_path', '')}".strip(" /"),
                "content": row["text"],
                "score": score,
                "keyword_score": float(keyword_scores[idx]),
                "embedding_score": float(embedding_scores[idx]) if embedding_scores is not None else None,
                "rule_score": float(rule_scores[idx]) if matched_rules else None,
                "matched_rules": matched_rules or None,
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
