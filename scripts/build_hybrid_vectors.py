from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

import joblib
import numpy as np
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from knowledge_base_paths import get_knowledge_base_root

from build_vectors import (
    BATCH_ID,
    CHUNKS_JSONL,
    PACKAGES_ROOT,
    RAG_ROOT,
    VECTORS_ROOT,
    build_sqlite,
    ensure_clean_dir,
    load_chunks,
    write_metadata_csv,
)


DEFAULT_EMBEDDING_DIM = 384
DEFAULT_EMBEDDING_SERVICE_URL = "http://127.0.0.1:9100"


def build_keyword_index(texts: list[str]):
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        min_df=2,
        max_features=100000,
        lowercase=False,
        norm="l2",
    )
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def build_lsa_embedding(keyword_matrix, dimension: int) -> tuple[np.ndarray, dict]:
    max_dimension = min(dimension, keyword_matrix.shape[0] - 1, keyword_matrix.shape[1] - 1)
    if max_dimension < 2:
        raise ValueError("not enough chunks/features to build dense LSA embedding")

    svd = TruncatedSVD(n_components=max_dimension, random_state=42)
    dense = svd.fit_transform(keyword_matrix)
    dense = normalize(dense, norm="l2").astype("float32")
    model_info = {
        "provider": "lsa",
        "components": svd.components_.astype("float32"),
        "dimension": max_dimension,
        "source": "tfidf_char_2_4",
    }
    return dense, model_info


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"embedding service returned {exc.code}: {body}") from exc


def build_service_embedding(
    texts: list[str],
    service_url: str,
    batch_size: int,
    timeout: int,
) -> tuple[np.ndarray, dict]:
    embeddings: list[list[float]] = []
    model_name = ""
    provider = "service"
    dimension = 0
    endpoint = service_url.rstrip("/") + "/embed"

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = _post_json(
            endpoint,
            {"texts": batch, "normalize": True, "input_type": "document"},
            timeout=timeout,
        )
        embeddings.extend(response["embeddings"])
        model_name = response.get("model", model_name)
        provider = response.get("provider", provider)
        dimension = int(response.get("dimension", dimension))
        print(f"embedded {min(start + len(batch), len(texts))}/{len(texts)}")

    matrix = np.asarray(embeddings, dtype="float32")
    matrix = normalize(matrix, norm="l2").astype("float32")
    model_info = {
        "provider": "service",
        "service_provider": provider,
        "model": model_name,
        "dimension": int(matrix.shape[1] if matrix.size else dimension),
        "build_service_url": service_url,
        "document_input_type": "document",
        "pooling": response.get("pooling") if texts else None,
    }
    return matrix, model_info


def write_manifest(rows: list[dict], keyword_matrix, embedding_matrix: np.ndarray, embedding_model: dict) -> Path:
    manifest_path = VECTORS_ROOT / "vector_manifest.json"
    stats = {
        "batch_id": BATCH_ID,
        "retrieval_strategy": "hybrid",
        "chunk_count": len(rows),
        "doc_count": len({r["doc_id"] for r in rows}),
        "keyword_index": {
            "type": "TfidfVectorizer",
            "analyzer": "char",
            "ngram_range": [2, 4],
            "norm": "l2",
            "matrix_shape": [keyword_matrix.shape[0], keyword_matrix.shape[1]],
        },
        "embedding_index": {
            "provider": embedding_model["provider"],
            "model": embedding_model.get("model"),
            "matrix_shape": [int(embedding_matrix.shape[0]), int(embedding_matrix.shape[1])],
            "norm": "l2",
        },
        "hybrid_default": {
            "keyword_weight": 0.6,
            "embedding_weight": 0.4,
            "rule_weight": 0.2,
            "query_expansion_enabled": True,
            "candidate_multiplier": 8,
        },
        "stored_files": {
            "keyword_matrix": str(VECTORS_ROOT / "keyword_matrix.npz"),
            "keyword_vectorizer": str(VECTORS_ROOT / "keyword_vectorizer.joblib"),
            "legacy_matrix": str(VECTORS_ROOT / "vector_matrix.npz"),
            "legacy_vectorizer": str(VECTORS_ROOT / "vectorizer.joblib"),
            "embedding_matrix": str(VECTORS_ROOT / "embedding_matrix.npy"),
            "embedding_model": str(VECTORS_ROOT / "embedding_model.joblib"),
            "sqlite": str(VECTORS_ROOT / "vector_index.sqlite"),
            "metadata_csv": str(VECTORS_ROOT / "vector_metadata.csv"),
        },
    }
    manifest_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (VECTORS_ROOT / "hybrid_manifest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def write_summary(rows: list[dict], keyword_matrix, embedding_matrix: np.ndarray, embedding_model: dict) -> Path:
    summary_path = RAG_ROOT / "hybrid_build_summary.md"
    folder_counts: dict[str, int] = {}
    doc_type_counts: dict[str, int] = {}
    for row in rows:
        folder_counts[row["folder"]] = folder_counts.get(row["folder"], 0) + 1
        doc_type_counts[row["doc_type"]] = doc_type_counts.get(row["doc_type"], 0) + 1

    lines = [
        f"# {BATCH_ID} Hybrid 检索索引构建摘要",
        "",
        f"- chunk 数：{len(rows)}",
        f"- 文档数：{len({r['doc_id'] for r in rows})}",
        f"- 关键词矩阵：{keyword_matrix.shape[0]} x {keyword_matrix.shape[1]}",
        f"- Embedding 矩阵：{embedding_matrix.shape[0]} x {embedding_matrix.shape[1]}",
        f"- Embedding provider：{embedding_model['provider']}",
        f"- Embedding model：{embedding_model.get('model') or '-'}",
        "",
        "## 文件夹分布",
    ]
    for k, v in folder_counts.items():
        lines.append(f"- {k}：{v}")
    lines.append("")
    lines.append("## 文档类型分布")
    for k, v in doc_type_counts.items():
        lines.append(f"- {k}：{v}")
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build keyword + embedding hybrid retrieval artifacts.")
    parser.add_argument(
        "--embedding-provider",
        choices=["lsa", "service"],
        default="lsa",
        help="Embedding provider. service calls the independent embedding-service.",
    )
    parser.add_argument("--embedding-dim", type=int, default=DEFAULT_EMBEDDING_DIM)
    parser.add_argument("--embedding-service-url", default=DEFAULT_EMBEDDING_SERVICE_URL)
    parser.add_argument("--embedding-batch-size", type=int, default=16)
    parser.add_argument("--embedding-timeout", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not CHUNKS_JSONL.exists():
        raise FileNotFoundError(f"missing chunks file: {CHUNKS_JSONL}")

    ensure_clean_dir(VECTORS_ROOT)
    ensure_clean_dir(RAG_ROOT)
    ensure_clean_dir(PACKAGES_ROOT)

    rows = load_chunks()
    texts = [row["text"] for row in rows]

    keyword_vectorizer, keyword_matrix = build_keyword_index(texts)
    if args.embedding_provider == "service":
        embedding_matrix, embedding_model = build_service_embedding(
            texts,
            service_url=args.embedding_service_url,
            batch_size=args.embedding_batch_size,
            timeout=args.embedding_timeout,
        )
    else:
        embedding_matrix, embedding_model = build_lsa_embedding(keyword_matrix, args.embedding_dim)

    sparse.save_npz(VECTORS_ROOT / "keyword_matrix.npz", keyword_matrix)
    joblib.dump(keyword_vectorizer, VECTORS_ROOT / "keyword_vectorizer.joblib")
    sparse.save_npz(VECTORS_ROOT / "vector_matrix.npz", keyword_matrix)
    joblib.dump(keyword_vectorizer, VECTORS_ROOT / "vectorizer.joblib")
    np.save(VECTORS_ROOT / "embedding_matrix.npy", embedding_matrix)
    joblib.dump(embedding_model, VECTORS_ROOT / "embedding_model.joblib", compress=3)

    sqlite_path = build_sqlite(rows)
    metadata_csv = write_metadata_csv(rows)
    manifest_path = write_manifest(rows, keyword_matrix, embedding_matrix, embedding_model)
    summary_path = write_summary(rows, keyword_matrix, embedding_matrix, embedding_model)

    package = {
        "batch_id": BATCH_ID,
        "retrieval_strategy": "hybrid",
        "vector_store": {
            "sqlite": str(sqlite_path),
            "keyword_matrix": str(VECTORS_ROOT / "keyword_matrix.npz"),
            "keyword_vectorizer": str(VECTORS_ROOT / "keyword_vectorizer.joblib"),
            "embedding_matrix": str(VECTORS_ROOT / "embedding_matrix.npy"),
            "embedding_model": str(VECTORS_ROOT / "embedding_model.joblib"),
            "metadata_csv": str(metadata_csv),
        },
        "summary": str(summary_path),
    }
    (PACKAGES_ROOT / "vector_package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"chunk count: {len(rows)}")
    print(f"keyword matrix shape: {keyword_matrix.shape}")
    print(f"embedding matrix shape: {embedding_matrix.shape}")
    print(f"sqlite: {sqlite_path}")
    print(f"manifest: {manifest_path}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
