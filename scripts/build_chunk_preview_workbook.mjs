import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const ROOT = process.env.KB_ROOT_DIR || "/Users/chenzhuo/hb/knowledge_base";
const BATCH_ID = process.env.KB_BATCH_ID || "batch_20260521";
const CHUNKS_ROOT = path.join(ROOT, "chunks", BATCH_ID);
const OUTPUT_DIR = path.join(ROOT, "outputs", "chunk_preview_batch_20260521");
const OUTPUT_FILE = path.join(OUTPUT_DIR, "chunks_preview.xlsx");

const chunkJsonlPath = path.join(CHUNKS_ROOT, "chunks.jsonl");
const chunkStatsPath = path.join(CHUNKS_ROOT, "chunk_stats.json");

function parseJsonl(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function prettyNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  if (Number.isInteger(value)) return value.toLocaleString("zh-CN");
  const num = Number(value);
  return Number.isFinite(num) ? num.toLocaleString("zh-CN") : String(value);
}

async function main() {
  const [jsonlText, statsText] = await Promise.all([
    fs.readFile(chunkJsonlPath, "utf8"),
    fs.readFile(chunkStatsPath, "utf8"),
  ]);
  const rows = parseJsonl(jsonlText);
  const stats = JSON.parse(statsText);

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("Summary");
  const preview = workbook.worksheets.add("Preview");

  const summaryRows = [
    ["知识库 chunk 预览", "", "", ""],
    ["批次", BATCH_ID, "", ""],
    ["selected 文档数", stats.selected_docs, "chunk 总数", stats.chunks],
    ["平均每文档 chunk 数", stats.avg_chunks_per_doc, "平均 chunk 字符数", stats.avg_chunk_chars],
    ["最小 chunk 字符数", stats.min_chunk_chars, "最大 chunk 字符数", stats.max_chunk_chars],
    ["解析器分布", "", "", ""],
    ["parser", "chunks", "", ""],
    ...Object.entries(stats.parser_counts || {}).map(([k, v]) => [k, v, "", ""]),
    ["文件夹分布", "", "", ""],
    ["folder", "chunks", "", ""],
    ...Object.entries(stats.folder_counts || {}).map(([k, v]) => [k, v, "", ""]),
  ];
  summary.getRange(`A1:D${summaryRows.length}`).values = summaryRows;
  summary.freezePanes.freezeRows(1);

  const previewHeaders = [
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
    "text_preview",
    "source_md",
    "selected_md",
  ];
  const previewRows = rows.map((row) => [
    row.chunk_id,
    row.doc_id,
    row.doc_seq,
    row.folder,
    row.doc_type,
    row.version,
    row.parser,
    row.chunk_index,
    row.chunk_count,
    row.char_count,
    row.page_start ?? "",
    row.page_end ?? "",
    row.section_path,
    row.section_path_end,
    row.text.slice(0, 180).replace(/\n/g, " "),
    row.source_md,
    row.selected_md,
  ]);
  preview.getRange(`A1:${String.fromCharCode(64 + previewHeaders.length)}${previewRows.length + 1}`).values = [
    previewHeaders,
    ...previewRows,
  ];
  preview.freezePanes.freezeRows(1);

  // Keep column widths sensible for quick inspection.
  preview.getRange("A:Q").columnWidth = 18;
  preview.getRange("M:N").columnWidth = 32;
  preview.getRange("O:Q").columnWidth = 42;
  summary.getRange("A:D").columnWidth = 24;

  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(OUTPUT_FILE);

  console.log(`saved ${OUTPUT_FILE}`);
  console.log(`rows ${rows.length}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
