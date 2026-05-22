from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from markitdown import MarkItDown


ROOT = Path("/Users/chenzhuo/hb/knowledge_base")
RAW_ROOT = ROOT / "raw" / "标准化体系_分类版"
STAGING_ROOT = ROOT / "staging" / "raw_02_07"
WORKING_ROOT = ROOT / "working"
BATCH_ID = "batch_20260521"
MINERU_OUT = WORKING_ROOT / "parsed" / BATCH_ID / "mineru"
MARKITDOWN_OUT = WORKING_ROOT / "parsed" / BATCH_ID / "markitdown_docx"
EVAL_OUT = WORKING_ROOT / "evaluation" / BATCH_ID
SELECTED_OUT = ROOT / "selected" / BATCH_ID
CHUNKS_OUT = ROOT / "chunks" / BATCH_ID
VECTORS_OUT = ROOT / "vectors" / BATCH_ID
RAG_OUT = ROOT / "rag" / BATCH_ID
PACKAGES_OUT = ROOT / "packages" / BATCH_ID
OPS_OUT = ROOT / "operations"
DOCS_OUT = ROOT / "docs"
ALLOWED_FOLDERS = [
    "02规章制度与标准规范",
    "03SOP流程化资料_疑似",
    "04表单台账与字段说明_疑似",
    "05岗位职责与角色资料",
    "06安全与应急资料",
    "07信息系统与APP操作",
]
PRIMARY_EXTS = {".pdf", ".docx", ".xlsx", ".pptx"}
SUPPLEMENT_EXTS = {".docx"}


@dataclass
class FileRecord:
    folder: str
    source_path: str
    ext: str
    file_name: str
    size_kb: float
    parser_primary: str
    parser_secondary: str
    mineru_md: str
    markitdown_md: str
    parse_state: str
    char_count: int
    line_count: int
    heading_count: int
    table_count: int
    score: int
    recommendation: str
    note: str


def ensure_dirs() -> None:
    for p in [
        STAGING_ROOT,
        MINERU_OUT,
        MARKITDOWN_OUT,
        EVAL_OUT,
        SELECTED_OUT,
        CHUNKS_OUT,
        VECTORS_OUT,
        RAG_OUT,
        PACKAGES_OUT,
        OPS_OUT,
        DOCS_OUT,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def link_staging() -> None:
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    for folder in ALLOWED_FOLDERS:
        src = RAW_ROOT / folder
        dst = STAGING_ROOT / folder
        if dst.exists() or dst.is_symlink():
            continue
        dst.symlink_to(src, target_is_directory=True)


def iter_source_files() -> Iterable[Path]:
    for folder in ALLOWED_FOLDERS:
        base = RAW_ROOT / folder
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if p.name.startswith(".") or p.name.startswith("~$"):
                continue
            if p.suffix.lower() in {".zip", ".csv", ".txt", ".md", ".xlsx", ".pdf", ".docx", ".pptx"}:
                yield p


def _safe_name(path: Path) -> str:
    stem = path.stem
    return re.sub(r"[\\/:*?\"<>|]", "_", stem)


def run_mineru_on_folder(folder: str) -> None:
    src = STAGING_ROOT / folder
    out = MINERU_OUT / folder
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        # keep previous runs only if user reruns intentionally with a new batch id
        pass
    cmd = [
        "mineru",
        "-p",
        str(src),
        "-o",
        str(out),
        "-b",
        "pipeline",
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[MinerU] folder failed but will continue: {folder} (returncode={result.returncode})")


def run_markitdown_docx(files: list[Path]) -> dict[str, Path]:
    md = MarkItDown()
    produced: dict[str, Path] = {}
    for src in files:
        rel_folder = src.parent.name
        dest_dir = MARKITDOWN_OUT / rel_folder / _safe_name(src)
        dest_dir.mkdir(parents=True, exist_ok=True)
        result = md.convert_local(str(src))
        markdown = result.markdown or result.text_content or ""
        (dest_dir / "content.md").write_text(markdown, encoding="utf-8")
        meta = {
            "source_path": str(src),
            "file_name": src.name,
            "parser": "markitdown",
            "title": result.title,
            "char_count": len(markdown),
            "line_count": markdown.count("\n") + 1 if markdown else 0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        (dest_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        produced[str(src)] = dest_dir / "content.md"
    return produced


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="ignore")


def detect_markdown_stats(text: str) -> tuple[int, int, int]:
    heading_count = len(re.findall(r"(?m)^#{1,6}\s+", text))
    table_count = text.count("|")
    line_count = text.count("\n") + 1 if text else 0
    return heading_count, table_count, line_count


def score_document(ext: str, char_count: int, heading_count: int, table_count: int) -> tuple[int, str]:
    score = 0
    if char_count > 0:
        score += 30
    if char_count > 1500:
        score += 20
    if heading_count >= 3:
        score += 20
    elif heading_count >= 1:
        score += 10
    if table_count >= 10:
        score += 10
    if ext == ".pdf":
        score += 10
    elif ext == ".docx":
        score += 8
    elif ext == ".xlsx":
        score += 6
    if char_count > 5000:
        score += 10
    if score >= 65:
        return score, "selected_candidate"
    if score >= 45:
        return score, "review_candidate"
    return score, "needs_review"


def parse_mineru_outputs(folder: str, source_files: list[Path]) -> list[FileRecord]:
    folder_root = MINERU_OUT / folder
    records: list[FileRecord] = []
    lookup = {f.stem: f for f in source_files}

    for stem, src in lookup.items():
        doc_dir = folder_root / stem / "auto"
        md_file = doc_dir / f"{stem}.md"
        md_text = read_text(md_file) if md_file.exists() else ""
        heading_count, table_count, line_count = detect_markdown_stats(md_text)
        char_count = len(md_text)
        score, recommendation = score_document(src.suffix.lower(), char_count, heading_count, table_count)
        meta = {
            "source_path": str(src),
            "folder": folder,
            "file_name": src.name,
            "parser_primary": "mineru",
            "mineru_md": str(md_file) if md_file.exists() else "",
            "char_count": char_count,
            "line_count": line_count,
            "heading_count": heading_count,
            "table_count": table_count,
            "score": score,
            "recommendation": recommendation,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(
            FileRecord(
                folder=folder,
                source_path=str(src),
                ext=src.suffix.lower().lstrip("."),
                file_name=src.name,
                size_kb=round(src.stat().st_size / 1024, 1),
                parser_primary="mineru",
                parser_secondary="markitdown" if src.suffix.lower() == ".docx" else "",
                mineru_md=str(md_file) if md_file.exists() else "",
                markitdown_md=str(MARKITDOWN_OUT / folder / _safe_name(src) / "content.md") if src.suffix.lower() == ".docx" else "",
                parse_state="done" if md_file.exists() else "missing_md",
                char_count=char_count,
                line_count=line_count,
                heading_count=heading_count,
                table_count=table_count,
                score=score,
                recommendation=recommendation,
                note="MinerU主解析，DOCX另存MarkItDown补充" if src.suffix.lower() == ".docx" else "MinerU主解析",
            )
        )
    return records


def write_evaluation(records: list[FileRecord]) -> None:
    EVAL_OUT.mkdir(parents=True, exist_ok=True)
    csv_path = EVAL_OUT / "parse_summary.csv"
    md_path = EVAL_OUT / "parse_summary.md"
    json_path = EVAL_OUT / "parse_summary.json"
    fieldnames = list(asdict(records[0]).keys()) if records else []
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow(asdict(rec))
    json_path.write_text(json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for rec in records:
        counts[rec.recommendation] = counts.get(rec.recommendation, 0) + 1
    lines = [
        f"# {BATCH_ID} 预处理汇总",
        "",
        f"- 总文件数：{len(records)}",
        f"- selected_candidate：{counts.get('selected_candidate', 0)}",
        f"- review_candidate：{counts.get('review_candidate', 0)}",
        f"- needs_review：{counts.get('needs_review', 0)}",
        "",
        "## 处理说明",
        "- 02-07 文件夹纳入本轮处理，01完整原始资料未纳入。",
        "- MinerU 作为主解析器；DOCX 同时保留 MarkItDown 补充稿。",
        "- Marker 作为后续抽样对比兜底，待模型/依赖统一后再接入本轮评估。",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    link_staging()

    folders = ALLOWED_FOLDERS
    all_files = list(iter_source_files())
    print(f"source files: {len(all_files)}")

    by_folder: dict[str, list[Path]] = {f: [] for f in folders}
    for p in all_files:
        by_folder[p.parent.name].append(p)

    records: list[FileRecord] = []

    # 1) MinerU 主处理
    for folder in folders:
        if not by_folder.get(folder):
            continue
        print(f"[MinerU] {folder}: {len(by_folder[folder])} files")
        run_mineru_on_folder(folder)

    # 2) MarkItDown 补充 DOCX
    docx_files = [p for p in all_files if p.suffix.lower() in SUPPLEMENT_EXTS]
    print(f"[MarkItDown] docx supplement: {len(docx_files)} files")
    run_markitdown_docx(docx_files)

    # 3) 解析结果汇总
    for folder in folders:
        if not by_folder.get(folder):
            continue
        records.extend(parse_mineru_outputs(folder, by_folder[folder]))

    records.sort(key=lambda r: (folders.index(r.folder), r.file_name))
    write_evaluation(records)

    # 4) 先生成 selected 候选清单目录，供后续人工筛选
    selected_candidates = [asdict(r) for r in records if r.recommendation == "selected_candidate"]
    (SELECTED_OUT / "candidate_list.json").write_text(json.dumps(selected_candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    (SELECTED_OUT / "candidate_list.md").write_text(
        "# selected 候选清单\n\n" + "\n".join(f"- {r['folder']} / {r['file_name']} / {r['score']}" for r in selected_candidates[:200]),
        encoding="utf-8",
    )

    # 5) 预留后续阶段目录
    for p in [CHUNKS_OUT, VECTORS_OUT, RAG_OUT]:
        (p / BATCH_ID).mkdir(parents=True, exist_ok=True)

    print(f"done: {len(records)} files processed")


if __name__ == "__main__":
    main()
