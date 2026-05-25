from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from knowledge_base_paths import get_knowledge_base_root
from knowledge_base_registry import load_registry, upsert_registry_item

from .config import settings
from .asset_manifest import record_asset_version
from .daily_report import build_daily_report, write_daily_report
from .operation_log import append_operation_event


PLATFORM_MEMORY_KB_ID = "platform_run_memory"
DEFAULT_MEMORY_BATCH_ID = settings.batch_id


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_name(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "untitled"


def ensure_platform_memory_registry(root_dir: Path | str) -> dict:
    root_dir = Path(root_dir)
    registry = load_registry(root_dir)
    memory_root = str(root_dir / "knowledge_bases" / PLATFORM_MEMORY_KB_ID)
    item = next((row for row in registry.get("items", []) if row.get("knowledge_base_id") == PLATFORM_MEMORY_KB_ID), None)
    payload = {
        "knowledge_base_id": PLATFORM_MEMORY_KB_ID,
        "name": "平台运行记忆库",
        "description": "自动接收每日操作日报，用于平台自进化与运行复盘。",
        "owner": "平台",
        "status": "standby",
        "root_dir": memory_root,
        "default_batch_id": DEFAULT_MEMORY_BATCH_ID,
        "doc_count": int(item.get("doc_count", 0) if item else 0),
        "chunk_count": int(item.get("chunk_count", 0) if item else 0),
    }
    return upsert_registry_item(root_dir, payload)


def _memory_root(root_dir: Path | str) -> Path:
    ensure_platform_memory_registry(root_dir)
    return get_knowledge_base_root(root_dir, PLATFORM_MEMORY_KB_ID)


def _split_markdown_into_chunks(markdown: str, max_chars: int = 1200) -> list[tuple[str, str]]:
    lines = [line.rstrip() for line in markdown.splitlines()]
    sections: list[tuple[str, list[str]]] = []
    current_heading = "概览"
    current_lines: list[str] = []

    heading_re = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")
    for line in lines:
        heading_match = heading_re.match(line)
        if heading_match:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = heading_match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))

    chunks: list[tuple[str, str]] = []
    for heading, section_lines in sections:
        text = "\n".join(section_lines).strip()
        if not text:
            continue
        if len(text) <= max_chars:
            chunks.append((heading, text))
            continue
        buf: list[str] = []
        buf_len = 0
        for paragraph in [p for p in text.split("\n\n") if p.strip()]:
            if len(paragraph) > max_chars:
                if buf:
                    chunks.append((heading, "\n\n".join(buf).strip()))
                    buf = []
                    buf_len = 0
                for start in range(0, len(paragraph), max_chars):
                    chunks.append((heading, paragraph[start : start + max_chars].strip()))
                continue
            projected = len(paragraph) + (2 if buf else 0) + buf_len
            if buf and projected > max_chars:
                chunks.append((heading, "\n\n".join(buf).strip()))
                buf = [paragraph]
                buf_len = len(paragraph)
            else:
                buf.append(paragraph)
                buf_len = projected
        if buf:
            chunks.append((heading, "\n\n".join(buf).strip()))
    return [(heading, chunk) for heading, chunk in chunks if chunk.strip()]


def _build_chunk_rows(report_date: str, report_path: Path, selected_md_path: Path, markdown: str) -> list[dict]:
    chunks = _split_markdown_into_chunks(markdown)
    chunk_count = len(chunks)
    rows: list[dict] = []
    for index, (heading, text) in enumerate(chunks, start=1):
        chunk_id = f"daily_{report_date}_c{index:03d}"
        rows.append(
            {
                "chunk_id": chunk_id,
                "doc_id": f"daily_{report_date}",
                "doc_seq": 1,
                "doc_name": f"知识平台日报 {report_date}",
                "folder": "operations",
                "file_name": f"{report_date}.md",
                "doc_type": "平台运行记忆",
                "knowledge_domain": "platform_memory",
                "version": "v1",
                "permissions": "internal",
                "source_file": str(report_path),
                "source_md": str(selected_md_path),
                "selected_md": str(selected_md_path),
                "parser": "system",
                "parse_state": "success",
                "recommendation": "daily_report",
                "score": 100,
                "chunk_index": index,
                "chunk_count": chunk_count,
                "section_path": heading,
                "section_path_end": heading,
                "page_start": None,
                "page_end": None,
                "char_count": len(text),
                "keywords": [heading][:10],
                "text": text,
            }
        )
    return rows


def _write_chunks_jsonl(memory_root: Path, rows: list[dict]) -> Path:
    chunks_root = memory_root / "chunks" / DEFAULT_MEMORY_BATCH_ID
    chunks_root.mkdir(parents=True, exist_ok=True)
    chunks_path = chunks_root / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")
    return chunks_path


def _write_sqlite(vectors_root: Path, rows: list[dict]) -> Path:
    db_path = vectors_root / "vector_index.sqlite"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS chunks;
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT,
            doc_seq INTEGER,
            folder TEXT,
            doc_type TEXT,
            version TEXT,
            parser TEXT,
            chunk_index INTEGER,
            chunk_count INTEGER,
            char_count INTEGER,
            page_start INTEGER,
            page_end INTEGER,
            section_path TEXT,
            section_path_end TEXT,
            source_file TEXT,
            source_md TEXT,
            selected_md TEXT,
            permissions TEXT,
            text TEXT
        );
        CREATE INDEX idx_chunks_doc_id ON chunks(doc_id);
        CREATE INDEX idx_chunks_folder ON chunks(folder);
        CREATE INDEX idx_chunks_doc_type ON chunks(doc_type);
        """
    )
    cur.executemany(
        """
        INSERT INTO chunks (
            chunk_id, doc_id, doc_seq, folder, doc_type, version, parser, chunk_index,
            chunk_count, char_count, page_start, page_end, section_path, section_path_end,
            source_file, source_md, selected_md, permissions, text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["chunk_id"],
                row["doc_id"],
                row["doc_seq"],
                row["folder"],
                row["doc_type"],
                row["version"],
                row["parser"],
                row["chunk_index"],
                row["chunk_count"],
                row["char_count"],
                row["page_start"],
                row["page_end"],
                row["section_path"],
                row["section_path_end"],
                row["source_file"],
                row["source_md"],
                row["selected_md"],
                row["permissions"],
                row["text"],
            )
            for row in rows
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def _write_metadata_csv(vectors_root: Path, rows: list[dict]) -> Path:
    csv_path = vectors_root / "vector_metadata.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "chunk_id",
                "doc_id",
                "doc_seq",
                "folder",
                "doc_type",
                "version",
                "parser",
                "chunk_index",
                "chunk_count",
                "char_count",
                "page_start",
                "page_end",
                "section_path",
                "section_path_end",
                "source_file",
                "source_md",
                "selected_md",
                "permissions",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})
    return csv_path


def _build_keyword_index(texts: list[str]):
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        min_df=1,
        max_features=50000,
        lowercase=False,
        norm="l2",
    )
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def _build_lsa_embedding(keyword_matrix, dimension: int = 64) -> tuple[np.ndarray, dict]:
    max_dimension = min(dimension, max(2, keyword_matrix.shape[0] - 1), max(2, keyword_matrix.shape[1] - 1))
    if max_dimension < 2:
        max_dimension = 2
    svd = TruncatedSVD(n_components=max_dimension, random_state=42)
    dense = svd.fit_transform(keyword_matrix)
    dense = normalize(dense, norm="l2").astype("float32")
    model_info = {
        "provider": "lsa",
        "components": svd.components_.astype("float32"),
        "dimension": max_dimension,
        "source": "daily_report_tfidf_char_2_4",
    }
    return dense, model_info


def _write_vector_artifacts(vectors_root: Path, rows: list[dict]) -> dict:
    texts = [row["text"] for row in rows]
    keyword_vectorizer, keyword_matrix = _build_keyword_index(texts)
    embedding_matrix, embedding_model = _build_lsa_embedding(keyword_matrix)

    sparse.save_npz(vectors_root / "keyword_matrix.npz", keyword_matrix)
    joblib.dump(keyword_vectorizer, vectors_root / "keyword_vectorizer.joblib")
    sparse.save_npz(vectors_root / "vector_matrix.npz", keyword_matrix)
    joblib.dump(keyword_vectorizer, vectors_root / "vectorizer.joblib")
    np.save(vectors_root / "embedding_matrix.npy", embedding_matrix)
    joblib.dump(embedding_model, vectors_root / "embedding_model.joblib", compress=3)

    sqlite_path = _write_sqlite(vectors_root, rows)
    metadata_csv_path = _write_metadata_csv(vectors_root, rows)
    manifest = {
        "batch_id": DEFAULT_MEMORY_BATCH_ID,
        "retrieval_strategy": "hybrid",
        "chunk_count": len(rows),
        "doc_count": len({row["doc_id"] for row in rows}),
        "keyword_index": {
            "type": "TfidfVectorizer",
            "analyzer": "char",
            "ngram_range": [2, 4],
            "norm": "l2",
            "matrix_shape": [int(keyword_matrix.shape[0]), int(keyword_matrix.shape[1])],
        },
        "embedding_index": {
            "provider": "lsa",
            "model": "daily_report_lsa",
            "matrix_shape": [int(embedding_matrix.shape[0]), int(embedding_matrix.shape[1])],
            "norm": "l2",
        },
        "stored_files": {
            "keyword_matrix": str(vectors_root / "keyword_matrix.npz"),
            "keyword_vectorizer": str(vectors_root / "keyword_vectorizer.joblib"),
            "legacy_matrix": str(vectors_root / "vector_matrix.npz"),
            "legacy_vectorizer": str(vectors_root / "vectorizer.joblib"),
            "embedding_matrix": str(vectors_root / "embedding_matrix.npy"),
            "embedding_model": str(vectors_root / "embedding_model.joblib"),
            "sqlite": str(sqlite_path),
            "metadata_csv": str(metadata_csv_path),
        },
    }
    (vectors_root / "vector_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (vectors_root / "hybrid_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (vectors_root.parent.parent / "rag").mkdir(parents=True, exist_ok=True)
    summary_path = vectors_root.parent.parent / "rag" / "hybrid_build_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                f"# {DEFAULT_MEMORY_BATCH_ID} 日报记忆索引构建摘要",
                "",
                f"- chunk 数：{len(rows)}",
                f"- 文档数：{len({row['doc_id'] for row in rows})}",
                f"- 关键词矩阵：{keyword_matrix.shape[0]} x {keyword_matrix.shape[1]}",
                f"- Embedding 矩阵：{embedding_matrix.shape[0]} x {embedding_matrix.shape[1]}",
                "- Embedding provider：lsa",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "vector_manifest": str(vectors_root / "vector_manifest.json"),
        "summary": str(summary_path),
        "sqlite": str(sqlite_path),
        "embedding_dim": int(embedding_matrix.shape[1]),
    }


def ingest_daily_report_to_memory(
    root_dir: Path | str,
    *,
    event_date: str | None = None,
    save_report: bool = True,
) -> dict:
    root_dir = Path(root_dir)
    report_payload = build_daily_report(root_dir, event_date=event_date)
    report_date = report_payload["event_date"]
    report_path = root_dir / "operations" / "daily" / f"{report_date}.md"
    if save_report:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_payload["content"], encoding="utf-8")
    else:
        # Ensure the report exists on disk for ingestion even if the caller only requested a dry build.
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_payload["content"], encoding="utf-8")
    record_asset_version(
        root_dir,
        knowledge_base_id="platform_run_memory",
        asset_type="daily_report",
        stage="report",
        logical_path=f"operations/daily/{report_date}.md",
        file_path=str(report_path),
        size_bytes=len(report_payload["content"].encode("utf-8")),
        created_by="system",
        metadata={"report_date": report_date, "source": "operations/daily-report"},
    )

    memory_root = _memory_root(root_dir)
    selected_md_path = memory_root / "selected" / DEFAULT_MEMORY_BATCH_ID / "documents" / report_date / "selected.md"
    selected_md_path.parent.mkdir(parents=True, exist_ok=True)
    selected_md_path.write_text(report_payload["content"], encoding="utf-8")
    record_asset_version(
        root_dir,
        knowledge_base_id=PLATFORM_MEMORY_KB_ID,
        asset_type="selected_md",
        stage="selected",
        logical_path=f"selected/{DEFAULT_MEMORY_BATCH_ID}/documents/{report_date}/selected.md",
        file_path=str(selected_md_path),
        size_bytes=len(report_payload["content"].encode("utf-8")),
        created_by="system",
        metadata={"report_date": report_date, "source_report": str(report_path)},
    )

    rows = _build_chunk_rows(report_date, report_path, selected_md_path, report_payload["content"])
    chunks_path = _write_chunks_jsonl(memory_root, rows)
    record_asset_version(
        root_dir,
        knowledge_base_id=PLATFORM_MEMORY_KB_ID,
        asset_type="chunk_jsonl",
        stage="chunks",
        logical_path=f"chunks/{DEFAULT_MEMORY_BATCH_ID}/chunks.jsonl",
        file_path=str(chunks_path),
        size_bytes=chunks_path.stat().st_size if chunks_path.exists() else 0,
        created_by="system",
        metadata={"report_date": report_date, "chunk_count": len(rows)},
    )
    vectors_root = memory_root / "vectors" / DEFAULT_MEMORY_BATCH_ID
    vectors_root.mkdir(parents=True, exist_ok=True)
    vector_artifacts = _write_vector_artifacts(vectors_root, rows)
    record_asset_version(
        root_dir,
        knowledge_base_id=PLATFORM_MEMORY_KB_ID,
        asset_type="vector_index",
        stage="vectors",
        logical_path=f"vectors/{DEFAULT_MEMORY_BATCH_ID}",
        file_path=str(vectors_root),
        created_by="system",
        metadata={"report_date": report_date, "chunk_count": len(rows), "vector_manifest": vector_artifacts["vector_manifest"]},
    )

    payload = {
        "knowledge_base_id": PLATFORM_MEMORY_KB_ID,
        "root_dir": str(memory_root),
        "report_path": str(report_path),
        "selected_md_path": str(selected_md_path),
        "chunks_path": str(chunks_path),
        "vectors_root": str(vectors_root),
        "chunk_count": len(rows),
        "doc_count": 1,
        "report_date": report_date,
        **vector_artifacts,
    }
    upsert_registry_item(
        root_dir,
        {
            "knowledge_base_id": PLATFORM_MEMORY_KB_ID,
            "name": "平台运行记忆库",
            "description": "自动接收每日操作日报，用于平台自进化与运行复盘。",
            "owner": "平台",
            "status": "standby",
            "root_dir": str(memory_root),
            "default_batch_id": DEFAULT_MEMORY_BATCH_ID,
            "doc_count": 1,
            "chunk_count": len(rows),
        },
    )
    append_operation_event(
        root_dir,
        event_type="daily_report_ingest",
        knowledge_base_id=PLATFORM_MEMORY_KB_ID,
        source="api/operations/daily-report/ingest",
        actor="system",
        input_assets=[
            {
                "stage": "daily_report",
                "kb_id": "",
                "file_path": str(report_path),
                "report_date": report_date,
            }
        ],
        output_assets=[
            {
                "stage": "selected",
                "kb_id": PLATFORM_MEMORY_KB_ID,
                "file_path": str(selected_md_path),
            },
            {
                "stage": "chunks",
                "kb_id": PLATFORM_MEMORY_KB_ID,
                "file_path": str(chunks_path),
            },
            {
                "stage": "vectors",
                "kb_id": PLATFORM_MEMORY_KB_ID,
                "file_path": str(vectors_root),
            },
        ],
        params={
            "report_date": report_date,
            "chunk_count": len(rows),
            "doc_count": 1,
        },
        status="success",
        remark="daily report ingested into platform memory",
    )
    return payload
