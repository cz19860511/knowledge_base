from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path("/Users/chenzhuo/hb/knowledge_base")
WORKING_ROOT = ROOT / "working"
SELECTED_ROOT = ROOT / "selected"
CHUNKS_ROOT = ROOT / "chunks"
EVAL_ROOT = WORKING_ROOT / "evaluation"
MINERU_OUT = WORKING_ROOT / "parsed"
MARKITDOWN_OUT = WORKING_ROOT / "parsed"
BATCH_ID = "batch_20260521"

RAW_BATCH_ROOT = ROOT / "raw" / "标准化体系_分类版"
PARSE_SUMMARY = EVAL_ROOT / BATCH_ID / "parse_summary.json"

SELECTED_BATCH_ROOT = SELECTED_ROOT / BATCH_ID
SELECTED_DOCS_ROOT = SELECTED_BATCH_ROOT / "documents"
CHUNKS_BATCH_ROOT = CHUNKS_ROOT / BATCH_ID

DOC_TYPE_MAP = {
    "02规章制度与标准规范": "制度规范",
    "03SOP流程化资料_疑似": "SOP流程",
    "04表单台账与字段说明_疑似": "表单台账",
    "05岗位职责与角色资料": "岗位职责",
    "06安全与应急资料": "安全应急",
    "07信息系统与APP操作": "系统操作",
}

FOLDER_ORDER = [
    "02规章制度与标准规范",
    "03SOP流程化资料_疑似",
    "04表单台账与字段说明_疑似",
    "05岗位职责与角色资料",
    "06安全与应急资料",
    "07信息系统与APP操作",
]

MAX_CHUNK_CHARS = 1800
MIN_CHUNK_CHARS = 300


@dataclass
class SelectedDoc:
    doc_id: str
    doc_seq: int
    folder: str
    file_name: str
    file_ext: str
    version: str
    doc_type: str
    knowledge_domain: str
    permissions: str
    source_path: str
    selected_md_path: str
    selected_md_source: str
    parser_primary: str
    parser_secondary: str
    parse_state: str
    recommendation: str
    score: int
    char_count: int
    heading_count: int
    table_count: int
    note: str


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    doc_seq: int
    doc_name: str
    folder: str
    file_name: str
    doc_type: str
    knowledge_domain: str
    version: str
    permissions: str
    source_file: str
    source_md: str
    selected_md: str
    parser: str
    parse_state: str
    recommendation: str
    score: int
    chunk_index: int
    chunk_count: int
    section_path: str
    section_path_end: str
    page_start: int | None
    page_end: int | None
    char_count: int
    keywords: list[str]
    text: str


def safe_name(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "untitled"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_parse_summary() -> list[dict]:
    if not PARSE_SUMMARY.exists():
        raise FileNotFoundError(f"parse summary not found: {PARSE_SUMMARY}")
    return json.loads(PARSE_SUMMARY.read_text(encoding="utf-8"))


def build_source_index(records: list[dict]) -> dict[str, dict]:
    return {item["source_path"]: item for item in records}


def doc_type_for_folder(folder: str) -> str:
    return DOC_TYPE_MAP.get(folder, folder)


def version_from_name(file_name: str) -> str:
    stem = Path(file_name).stem
    m = re.search(r"(v\d+(?:\.\d+)*)", stem, re.IGNORECASE)
    return m.group(1) if m else ""


def extract_keywords(*parts: str) -> list[str]:
    tokens: list[str] = []
    for part in parts:
        for raw in re.split(r"[\/／,，;；、\s]+", part or ""):
            token = raw.strip().strip("#:-()（）")
            if len(token) < 2:
                continue
            if token not in tokens:
                tokens.append(token)
    return tokens[:10]


def detect_stats(text: str) -> tuple[int, int, int]:
    heading_count = len(re.findall(r"(?m)^#{1,6}\s+", text))
    table_count = text.count("|")
    line_count = text.count("\n") + 1 if text else 0
    return heading_count, table_count, line_count


def quality_score(text: str) -> tuple[int, int, int, int]:
    heading_count, table_count, _ = detect_stats(text)
    char_count = len(text)
    score = 0
    if char_count > 0:
        score += 20
    if char_count > 500:
        score += 20
    if char_count > 1500:
        score += 20
    if heading_count >= 3:
        score += 25
    elif heading_count >= 1:
        score += 10
    if table_count >= 10:
        score += 10
    if char_count > 5000:
        score += 10
    return score, char_count, heading_count, table_count


def find_markdown_candidates(src: Path) -> list[tuple[Path, str]]:
    folder = src.parent.name
    stem = src.stem
    candidates: list[tuple[Path, str]] = []

    mineru_folder = WORKING_ROOT / "parsed" / BATCH_ID / "mineru" / folder
    if mineru_folder.exists():
        for match in mineru_folder.rglob(f"{stem}.md"):
            candidates.append((match, "mineru"))

    markitdown_docx = WORKING_ROOT / "parsed" / BATCH_ID / "markitdown_docx" / folder / safe_name(src.stem) / "content.md"
    if markitdown_docx.exists():
        candidates.append((markitdown_docx, "markitdown"))

    uniq: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path, parser in candidates:
        if path in seen:
            continue
        seen.add(path)
        uniq.append((path, parser))
    return uniq


def choose_best_markdown(src: Path) -> tuple[Path | None, str, int, int, int]:
    candidates = find_markdown_candidates(src)
    if not candidates:
        return None, "", 0, 0, 0

    ranked: list[tuple[int, int, int, int, Path, str, str]] = []
    for path, parser in candidates:
        text = normalize_text(read_text(path))
        score, char_count, heading_count, table_count = quality_score(text)
        # Prefer MinerU when scores are close; it is the primary parser in this batch.
        parser_bonus = 50 if parser == "mineru" else 0
        ranked.append((score + parser_bonus, char_count, heading_count, table_count, path, parser, text))
    ranked.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
    best = ranked[0]
    return best[4], best[5], best[1], best[2], best[3]


def split_long_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) > 1:
        parts: list[str] = []
        buf: list[str] = []
        buf_len = 0
        for line in lines:
            line_parts = [line[i : i + max_chars] for i in range(0, len(line), max_chars)] if len(line) > max_chars else [line]
            for line_part in line_parts:
                if buf and buf_len + len(line_part) + 1 > max_chars:
                    parts.append("\n".join(buf).strip())
                    buf = [line_part]
                    buf_len = len(line_part)
                else:
                    buf.append(line_part)
                    buf_len += len(line_part) + 1
        if buf:
            parts.append("\n".join(buf).strip())
        return [part for part in parts if part]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def split_units(markdown: str) -> list[dict]:
    page_re = re.compile(r"^\s*<!--\s*page:\s*(\d+)\s*-->\s*$")
    heading_re = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")

    units: list[dict] = []
    heading_stack: list[str] = []
    current_page: int | None = None
    paragraph_buf: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_buf
        if not paragraph_buf:
            return
        text = "\n".join(paragraph_buf).strip()
        paragraph_buf = []
        if not text:
            return
        units.append(
            {
                "kind": "paragraph",
                "text": text,
                "section_path": " / ".join(heading_stack),
                "page": current_page,
            }
        )

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            continue
        page_match = page_re.match(line)
        if page_match:
            flush_paragraph()
            current_page = int(page_match.group(1))
            continue
        heading_match = heading_re.match(line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            while len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(heading_text)
            units.append(
                {
                    "kind": "heading",
                    "text": f"{'#' * level} {heading_text}",
                    "section_path": " / ".join(heading_stack),
                    "page": current_page,
                }
            )
            continue
        paragraph_buf.append(line)

    flush_paragraph()
    return units


def build_chunks_from_text(markdown: str, max_chars: int = MAX_CHUNK_CHARS, min_chars: int = MIN_CHUNK_CHARS) -> list[dict]:
    units = split_units(markdown)
    chunks: list[dict] = []
    current: list[dict] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        chunk_text = "\n\n".join(item["text"] for item in current).strip()
        if chunk_text:
            pages = [item["page"] for item in current if item.get("page") is not None]
            chunks.append(
                {
                    "text": chunk_text,
                    "section_path": current[0].get("section_path", ""),
                    "section_path_end": current[-1].get("section_path", ""),
                    "page_start": min(pages) if pages else None,
                    "page_end": max(pages) if pages else None,
                    "unit_count": len(current),
                }
            )
        current = []
        current_len = 0

    for unit in units:
        text = unit["text"].strip()
        if not text:
            continue

        if len(text) > max_chars:
            flush()
            for part in split_long_text(text, max_chars):
                chunk_piece = {
                    "text": part,
                    "section_path": unit.get("section_path", ""),
                    "section_path_end": unit.get("section_path", ""),
                    "page_start": unit.get("page"),
                    "page_end": unit.get("page"),
                    "unit_count": 1,
                }
                chunks.append(chunk_piece)
            continue

        if unit["kind"] == "heading" and current and current_len >= min_chars:
            flush()

        projected = current_len + len(text) + (2 if current else 0)
        if current and projected > max_chars and current_len >= min_chars:
            flush()

        current.append(unit)
        current_len += len(text) + (2 if len(current) > 1 else 0)

    flush()
    return chunks


def ensure_clean_outputs() -> None:
    if SELECTED_DOCS_ROOT.exists():
        shutil.rmtree(SELECTED_DOCS_ROOT)
    SELECTED_DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    if CHUNKS_BATCH_ROOT.exists():
        shutil.rmtree(CHUNKS_BATCH_ROOT)
    CHUNKS_BATCH_ROOT.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    records = load_parse_summary()
    source_index = build_source_index(records)

    ensure_clean_outputs()

    ordered = sorted(records, key=lambda x: (FOLDER_ORDER.index(x["folder"]), x["file_name"]))
    selected_rows: list[SelectedDoc] = []
    chunk_rows: list[ChunkRecord] = []
    preview_rows: list[dict] = []

    for seq, item in enumerate(ordered, 1):
        src = Path(item["source_path"])
        best_md, parser, char_count, heading_count, table_count = choose_best_markdown(src)
        if best_md is None:
            print(f"[skip] no markdown found: {src}")
            continue

        folder = item["folder"]
        file_name = item["file_name"]
        doc_type = doc_type_for_folder(folder)
        knowledge_domain = folder
        version = version_from_name(file_name)
        permissions = "internal"
        doc_id = f"{BATCH_ID}_{seq:03d}"
        doc_slug = f"{seq:03d}_{safe_name(Path(file_name).stem)}"
        doc_dir = SELECTED_DOCS_ROOT / doc_slug
        doc_dir.mkdir(parents=True, exist_ok=True)

        selected_md_path = doc_dir / "selected.md"
        selected_meta_path = doc_dir / "selected_meta.json"
        selected_text = normalize_text(read_text(best_md))
        write_text(selected_md_path, selected_text + "\n")

        selected_meta = {
            "doc_id": doc_id,
            "doc_seq": seq,
            "folder": folder,
            "file_name": file_name,
            "file_ext": src.suffix.lower().lstrip("."),
            "source_path": str(src),
            "selected_md_source": str(best_md),
            "selected_md_parser": parser,
            "version": version,
            "doc_type": doc_type,
            "knowledge_domain": knowledge_domain,
            "permissions": permissions,
            "parser_primary": item.get("parser_primary", ""),
            "parser_secondary": item.get("parser_secondary", ""),
            "parse_state": item.get("parse_state", ""),
            "recommendation": item.get("recommendation", ""),
            "score": item.get("score", 0),
            "char_count": char_count,
            "heading_count": heading_count,
            "table_count": table_count,
            "note": item.get("note", ""),
        }
        write_text(selected_meta_path, json.dumps(selected_meta, ensure_ascii=False, indent=2))

        selected_rows.append(
            SelectedDoc(
                doc_id=doc_id,
                doc_seq=seq,
                folder=folder,
                file_name=file_name,
                file_ext=src.suffix.lower().lstrip("."),
                version=version,
                doc_type=doc_type,
                knowledge_domain=knowledge_domain,
                permissions=permissions,
                source_path=str(src),
                selected_md_path=str(selected_md_path),
                selected_md_source=str(best_md),
                parser_primary=item.get("parser_primary", ""),
                parser_secondary=item.get("parser_secondary", ""),
                parse_state=item.get("parse_state", ""),
                recommendation=item.get("recommendation", ""),
                score=int(item.get("score", 0)),
                char_count=char_count,
                heading_count=heading_count,
                table_count=table_count,
                note=item.get("note", ""),
            )
        )

        chunks = build_chunks_from_text(selected_text)
        if not chunks:
            chunks = [
                {
                    "text": selected_text[:MAX_CHUNK_CHARS],
                    "section_path": "",
                    "section_path_end": "",
                    "page_start": None,
                    "page_end": None,
                    "unit_count": 1,
                }
            ]

        for chunk_idx, chunk in enumerate(chunks, 1):
            chunk_id = f"{doc_id}_c{chunk_idx:03d}"
            keywords = extract_keywords(folder, doc_type, chunk.get("section_path", ""), chunk.get("section_path_end", ""), version)
            chunk_rows.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    doc_seq=seq,
                    doc_name=file_name,
                    folder=folder,
                    file_name=file_name,
                    doc_type=doc_type,
                    knowledge_domain=knowledge_domain,
                    version=version,
                    permissions=permissions,
                    source_file=str(src),
                    source_md=str(best_md),
                    selected_md=str(selected_md_path),
                    parser=parser,
                    parse_state=item.get("parse_state", ""),
                    recommendation=item.get("recommendation", ""),
                    score=int(item.get("score", 0)),
                    chunk_index=chunk_idx,
                    chunk_count=len(chunks),
                    section_path=chunk.get("section_path", ""),
                    section_path_end=chunk.get("section_path_end", ""),
                    page_start=chunk.get("page_start"),
                    page_end=chunk.get("page_end"),
                    char_count=len(chunk["text"]),
                    keywords=keywords,
                    text=chunk["text"],
                )
            )
            preview_rows.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "doc_seq": seq,
                    "folder": folder,
                    "doc_type": doc_type,
                    "version": version,
                    "parser": parser,
                    "chunk_index": chunk_idx,
                    "chunk_count": len(chunks),
                    "char_count": len(chunk["text"]),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "section_path": chunk.get("section_path", ""),
                    "section_path_end": chunk.get("section_path_end", ""),
                    "text_preview": chunk["text"][:160].replace("\n", " "),
                    "selected_md": str(selected_md_path),
                    "source_md": str(best_md),
                }
            )

        print(f"[chunked] {seq:03d} {file_name} -> {len(chunks)} chunks via {parser}")

    # Write selected manifest
    selected_manifest_path = SELECTED_BATCH_ROOT / "selected_manifest.json"
    selected_manifest_md = SELECTED_BATCH_ROOT / "selected_manifest.md"
    selected_manifest_path.write_text(
        json.dumps([asdict(row) for row in selected_rows], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    selected_summary = [
        f"# {BATCH_ID} selected 主文档清单",
        "",
        f"- 文档数：{len(selected_rows)}",
        f"- selected 目录：{SELECTED_DOCS_ROOT}",
        "",
        "## 说明",
        "- 以 MinerU 结果为主，缺失时回退 MarkItDown。",
        "- 每份文档保存为 `selected.md` 和 `selected_meta.json`。",
    ]
    selected_manifest_md.write_text("\n".join(selected_summary), encoding="utf-8")

    # Write chunk outputs
    chunks_jsonl = CHUNKS_BATCH_ROOT / "chunks.jsonl"
    chunk_stats_path = CHUNKS_BATCH_ROOT / "chunk_stats.json"
    preview_csv = CHUNKS_BATCH_ROOT / "chunks_preview.csv"
    preview_md = CHUNKS_BATCH_ROOT / "chunks_preview.md"

    with chunks_jsonl.open("w", encoding="utf-8") as f:
        for row in chunk_rows:
            f.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")

    # Stats
    doc_chunk_counts: dict[str, int] = {}
    chunk_sizes: list[int] = []
    parser_counts: dict[str, int] = {}
    folder_counts: dict[str, int] = {}
    for row in chunk_rows:
        doc_chunk_counts[row.doc_id] = doc_chunk_counts.get(row.doc_id, 0) + 1
        chunk_sizes.append(row.char_count)
        parser_counts[row.parser] = parser_counts.get(row.parser, 0) + 1
        folder_counts[row.folder] = folder_counts.get(row.folder, 0) + 1

    stats = {
        "batch_id": BATCH_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_docs": len(selected_rows),
        "chunks": len(chunk_rows),
        "docs_with_chunks": len(doc_chunk_counts),
        "avg_chunks_per_doc": round(len(chunk_rows) / len(selected_rows), 2) if selected_rows else 0,
        "avg_chunk_chars": round(sum(chunk_sizes) / len(chunk_sizes), 2) if chunk_sizes else 0,
        "min_chunk_chars": min(chunk_sizes) if chunk_sizes else 0,
        "max_chunk_chars": max(chunk_sizes) if chunk_sizes else 0,
        "parser_counts": parser_counts,
        "folder_counts": folder_counts,
        "doc_chunk_counts": doc_chunk_counts,
    }
    chunk_stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    with preview_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(preview_rows[0].keys()) if preview_rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in preview_rows:
            writer.writerow(row)

    preview_lines = [
        f"# {BATCH_ID} chunk 预览",
        "",
        f"- 文档数：{len(selected_rows)}",
        f"- chunk 数：{len(chunk_rows)}",
        f"- 平均 chunk 长度：{stats['avg_chunk_chars']}",
        "",
        "## 文件",
        f"- chunks.jsonl：{chunks_jsonl}",
        f"- chunks_preview.csv：{preview_csv}",
        f"- chunk_stats.json：{chunk_stats_path}",
    ]
    preview_md.write_text("\n".join(preview_lines), encoding="utf-8")

    print(f"selected docs: {len(selected_rows)}")
    print(f"chunks: {len(chunk_rows)}")
    print(f"selected manifest: {selected_manifest_path}")
    print(f"chunk jsonl: {chunks_jsonl}")


if __name__ == "__main__":
    main()
