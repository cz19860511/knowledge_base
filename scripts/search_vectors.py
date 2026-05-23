from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import joblib
from scipy import sparse


ROOT = Path(os.getenv("KB_ROOT_DIR", "/Users/chenzhuo/hb/knowledge_base"))
BATCH_ID = os.getenv("KB_BATCH_ID", "batch_20260521")
VECTORS_ROOT = ROOT / "vectors" / BATCH_ID


def load_metadata(chunk_ids: list[str]) -> dict[str, dict]:
    db_path = VECTORS_ROOT / "vector_index.sqlite"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in chunk_ids)
    query = f"""
        SELECT chunk_id, doc_id, doc_seq, folder, doc_type, version, parser,
               chunk_index, chunk_count, char_count, page_start, page_end,
               section_path, section_path_end, source_file, source_md, selected_md,
               permissions, text
        FROM chunks
        WHERE chunk_id IN ({placeholders})
    """
    rows = cur.execute(query, chunk_ids).fetchall()
    conn.close()
    result: dict[str, dict] = {}
    for row in rows:
        result[row[0]] = {
            "chunk_id": row[0],
            "doc_id": row[1],
            "doc_seq": row[2],
            "folder": row[3],
            "doc_type": row[4],
            "version": row[5],
            "parser": row[6],
            "chunk_index": row[7],
            "chunk_count": row[8],
            "char_count": row[9],
            "page_start": row[10],
            "page_end": row[11],
            "section_path": row[12],
            "section_path_end": row[13],
            "source_file": row[14],
            "source_md": row[15],
            "selected_md": row[16],
            "permissions": row[17],
            "text": row[18],
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="query text")
    parser.add_argument("--topk", type=int, default=5)
    args = parser.parse_args()

    vectorizer = joblib.load(VECTORS_ROOT / "vectorizer.joblib")
    matrix = sparse.load_npz(VECTORS_ROOT / "vector_matrix.npz")

    q_vec = vectorizer.transform([args.query])
    scores = (matrix @ q_vec.T).toarray().ravel()
    top_idx = scores.argsort()[::-1][: args.topk]

    chunk_ids = []
    score_map = {}
    with (ROOT / "chunks" / BATCH_ID / "chunks.jsonl").open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx in top_idx:
                import json

                row = json.loads(line)
                chunk_ids.append(row["chunk_id"])
                score_map[row["chunk_id"]] = float(scores[idx])

    metas = load_metadata(chunk_ids)
    for rank, cid in enumerate(chunk_ids, 1):
        meta = metas.get(cid)
        if not meta:
            continue
        print(f"#{rank} score={score_map[cid]:.4f} {meta['doc_type']} | {meta['folder']} | {meta['section_path']}")
        print(meta["text"][:300].replace("\n", " "))
        print("-" * 80)


if __name__ == "__main__":
    main()
