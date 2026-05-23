from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import OrderedDict
from pathlib import Path

import joblib
from scipy import sparse


ROOT = Path(os.getenv("KB_ROOT_DIR", "/Users/chenzhuo/hb/knowledge_base"))
BATCH_ID = os.getenv("KB_BATCH_ID", "batch_20260521")
VECTORS_ROOT = ROOT / "vectors" / BATCH_ID
CHUNKS_JSONL = ROOT / "chunks" / BATCH_ID / "chunks.jsonl"


def load_chunks_by_index() -> list[dict]:
    rows: list[dict] = []
    with CHUNKS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_metadata(chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
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


def extract_terms(query: str) -> list[str]:
    parts = re.split(r"[^\w\u4e00-\u9fff]+", query)
    terms = []
    for part in parts:
        part = part.strip()
        if len(part) < 2:
            continue
        if part not in terms:
            terms.append(part)
    if not terms:
        terms = list(dict.fromkeys([c for c in query if c.strip()]))
    return terms[:8]


def split_sentences(text: str) -> list[str]:
    text = text.replace("\n", " ")
    pieces = re.split(r"(?<=[。！？；;])\s*", text)
    return [p.strip() for p in pieces if p.strip()]


def score_sentence(sentence: str, terms: list[str]) -> int:
    score = 0
    for term in terms:
        if term and term in sentence:
            score += 3 if len(term) > 1 else 1
    return score


def build_answer(query: str, top_rows: list[dict], metadata: dict[str, dict]) -> str:
    terms = extract_terms(query)
    collected: list[tuple[int, dict, str]] = []
    for row in top_rows:
        meta = metadata.get(row["chunk_id"])
        if not meta:
            continue
        for sentence in split_sentences(meta["text"]):
            s = score_sentence(sentence, terms)
            if s > 0:
                collected.append((s, meta, sentence))
        if len(collected) >= 10:
            break

    if collected:
        collected.sort(key=lambda x: x[0], reverse=True)
        top_sentences = []
        seen = set()
        for _, meta, sentence in collected:
            key = (meta["doc_id"], sentence[:80])
            if key in seen:
                continue
            seen.add(key)
            top_sentences.append((meta, sentence))
            if len(top_sentences) >= 3:
                break
        answer_lines = ["根据已检索到的资料，",]
        for meta, sentence in top_sentences:
            answer_lines.append(f"- {sentence}")
        return "".join(answer_lines)

    if top_rows:
        first = metadata.get(top_rows[0]["chunk_id"])
        if first:
            snippet = first["text"][:220].replace("\n", " ")
            return f"已检索到相关资料，但未命中足够明确的条款句子。可先参考：{snippet}"
    return "未检索到足够相关的内容。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="query text")
    parser.add_argument("--topk", type=int, default=5)
    args = parser.parse_args()

    vectorizer = joblib.load(VECTORS_ROOT / "vectorizer.joblib")
    matrix = sparse.load_npz(VECTORS_ROOT / "vector_matrix.npz")
    chunks = load_chunks_by_index()

    q_vec = vectorizer.transform([args.query])
    scores = (matrix @ q_vec.T).toarray().ravel()
    top_idx = scores.argsort()[::-1][: args.topk]

    top_rows = [chunks[i] for i in top_idx]
    chunk_ids = [row["chunk_id"] for row in top_rows]
    metadata = load_metadata(chunk_ids)

    answer = build_answer(args.query, top_rows, metadata)
    print("# 回答")
    print(answer)
    print()
    print("# 引用来源")

    seen_docs = OrderedDict()
    for rank, idx in enumerate(top_idx, 1):
        row = chunks[idx]
        meta = metadata.get(row["chunk_id"])
        if not meta:
            continue
        doc_key = meta["doc_id"]
        if doc_key in seen_docs:
            continue
        seen_docs[doc_key] = True
        print(f"{rank}. {meta['doc_type']} | {meta['folder']} | {meta['section_path']} | {meta['source_file']}")
        print(f"   片段：{meta['text'][:240].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()
