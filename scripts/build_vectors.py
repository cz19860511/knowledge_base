from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer


ROOT = Path("/Users/chenzhuo/hb/knowledge_base")
BATCH_ID = "batch_20260521"
CHUNKS_JSONL = ROOT / "chunks" / BATCH_ID / "chunks.jsonl"
VECTORS_ROOT = ROOT / "vectors" / BATCH_ID
RAG_ROOT = ROOT / "rag" / BATCH_ID
PACKAGES_ROOT = ROOT / "packages" / BATCH_ID


@dataclass
class VectorRow:
    chunk_id: str
    doc_id: str
    doc_seq: int
    folder: str
    doc_type: str
    version: str
    parser: str
    chunk_index: int
    chunk_count: int
    char_count: int
    page_start: int | None
    page_end: int | None
    section_path: str
    section_path_end: str
    source_file: str
    source_md: str
    selected_md: str
    permissions: str
    text: str


def load_chunks() -> list[dict]:
    rows: list[dict] = []
    with CHUNKS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def ensure_clean_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_sqlite(rows: list[dict]) -> Path:
    db_path = VECTORS_ROOT / "vector_index.sqlite"
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
    rows_to_insert = [
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
    ]
    cur.executemany(
        """
        INSERT INTO chunks (
            chunk_id, doc_id, doc_seq, folder, doc_type, version, parser, chunk_index,
            chunk_count, char_count, page_start, page_end, section_path, section_path_end,
            source_file, source_md, selected_md, permissions, text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows_to_insert,
    )
    conn.commit()
    conn.close()
    return db_path


def write_metadata_csv(rows: list[dict]) -> Path:
    csv_path = VECTORS_ROOT / "vector_metadata.csv"
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
            writer.writerow({k: row.get(k) for k in writer.fieldnames})
    return csv_path


def write_vector_manifest(rows: list[dict], matrix) -> Path:
    manifest_path = VECTORS_ROOT / "vector_manifest.json"
    stats = {
        "batch_id": BATCH_ID,
        "chunk_count": len(rows),
        "doc_count": len({r["doc_id"] for r in rows}),
        "matrix_shape": [matrix.shape[0], matrix.shape[1]],
        "vectorizer": "TfidfVectorizer",
        "analyzer": "char",
        "ngram_range": [2, 4],
        "norm": "l2",
        "stored_files": {
            "matrix": str(VECTORS_ROOT / "vector_matrix.npz"),
            "vectorizer": str(VECTORS_ROOT / "vectorizer.joblib"),
            "sqlite": str(VECTORS_ROOT / "vector_index.sqlite"),
            "metadata_csv": str(VECTORS_ROOT / "vector_metadata.csv"),
        },
    }
    manifest_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def build_rag_summary(rows: list[dict], matrix) -> Path:
    summary_path = RAG_ROOT / "vector_build_summary.md"
    folder_counts: dict[str, int] = {}
    doc_type_counts: dict[str, int] = {}
    for row in rows:
        folder_counts[row["folder"]] = folder_counts.get(row["folder"], 0) + 1
        doc_type_counts[row["doc_type"]] = doc_type_counts.get(row["doc_type"], 0) + 1

    lines = [
        f"# {BATCH_ID} 向量库构建摘要",
        "",
        f"- chunk 数：{len(rows)}",
        f"- 文档数：{len({r['doc_id'] for r in rows})}",
        f"- 向量矩阵：{matrix.shape[0]} x {matrix.shape[1]}",
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


def main() -> None:
    if not CHUNKS_JSONL.exists():
        raise FileNotFoundError(f"missing chunks file: {CHUNKS_JSONL}")

    ensure_clean_dir(VECTORS_ROOT)
    ensure_clean_dir(RAG_ROOT)
    ensure_clean_dir(PACKAGES_ROOT)

    rows = load_chunks()
    texts = [row["text"] for row in rows]

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        min_df=2,
        max_features=100000,
        lowercase=False,
        norm="l2",
    )
    matrix = vectorizer.fit_transform(texts)

    sparse.save_npz(VECTORS_ROOT / "vector_matrix.npz", matrix)
    joblib.dump(vectorizer, VECTORS_ROOT / "vectorizer.joblib")
    sqlite_path = build_sqlite(rows)
    metadata_csv = write_metadata_csv(rows)
    manifest_path = write_vector_manifest(rows, matrix)
    summary_path = build_rag_summary(rows, matrix)

    package = {
        "batch_id": BATCH_ID,
        "vector_store": {
            "sqlite": str(sqlite_path),
            "matrix": str(VECTORS_ROOT / "vector_matrix.npz"),
            "vectorizer": str(VECTORS_ROOT / "vectorizer.joblib"),
            "metadata_csv": str(metadata_csv),
        },
        "summary": str(summary_path),
    }
    (PACKAGES_ROOT / "vector_package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"chunk count: {len(rows)}")
    print(f"matrix shape: {matrix.shape}")
    print(f"sqlite: {sqlite_path}")
    print(f"manifest: {manifest_path}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
