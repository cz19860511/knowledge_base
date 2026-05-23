import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const ROOT = process.env.KB_ROOT_DIR || "/Users/chenzhuo/hb/knowledge_base";
const INPUT_JSON = "/private/tmp/raw_inventory_rows.json";
const OUTPUT_DIR = path.join(ROOT, "outputs");
const OUTPUT_FILE = path.join(OUTPUT_DIR, "标准化体系_分类版_文件清单.xlsx");

const folderOrder = [
  "02规章制度与标准规范",
  "03SOP流程化资料_疑似",
  "04表单台账与字段说明_疑似",
  "05岗位职责与角色资料",
  "06安全与应急资料",
  "07信息系统与APP操作",
];

const folderNote = {
  "02规章制度与标准规范": "标准/制度类，适合作为知识库正式口径与引用底座。",
  "03SOP流程化资料_疑似": "流程/SOP类，适合抽取步骤、角色、时点和例外处理。",
  "04表单台账与字段说明_疑似": "台账/字段类，适合抽字段、口径、表头结构和填报规则。",
  "05岗位职责与角色资料": "岗位职责类，适合提炼职责边界、交接关系和考核要求。",
  "06安全与应急资料": "安全/应急类，适合整理触发条件、响应分级、处置流程和报送链路。",
  "07信息系统与APP操作": "系统操作类，适合提炼入口、页面路径、按钮动作和常见操作问题。",
};

const typeAnalysis = {
  "规章制度/标准": "标准/制度类，优先按条款结构、标准号和适用范围整理，适合作为正式问答引用底座。",
  "SOP/流程规范": "流程类资料，适合抽取步骤、责任人、时点和例外处理，后续可直接切 chunk。",
  "台账/字段说明": "台账/字段类，适合抽字段、口径、表头结构和填报规则，便于支撑表单问答。",
  "岗位职责": "岗位职责类，适合提炼职责边界、交接关系和考核要求，便于角色与权限梳理。",
  "安全/应急": "安全/应急类，适合整理触发条件、响应分级、处置流程和报送链路。",
  "信息系统/APP": "系统操作类，适合提炼入口、页面路径、按钮动作和常见操作问题。",
};

const extAnalysis = {
  pdf: "PDF 版本，通常更接近正式定版或对外发布版本，优先保留原始版式和页码信息。",
  docx: "DOCX 版本，通常更适合流程、制度和操作说明类内容，便于后续切片和重排。",
  xlsx: "表格类文件，重点关注字段、台账和汇总口径，后续可转成结构化表单知识。",
  txt: "文本类文件，可作为辅助说明或抽取中间产物，不建议单独作为正式知识底座。",
  csv: "结构化清单类文件，可用于辅助盘点或元数据整理。",
  zip: "压缩包，通常是打包产物，不直接作为知识内容入库。",
};

function colName(index) {
  let n = index + 1;
  let s = "";
  while (n > 0) {
    const mod = (n - 1) % 26;
    s = String.fromCharCode(65 + mod) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function normalizeTopic(topic, fileName) {
  if (topic) return topic;
  const name = fileName || "";
  const keywords = [
    "安全", "应急", "消防", "培训", "岗位", "职责", "流程", "制度", "标准",
    "APP", "系统", "操作", "表单", "台账", "投诉", "保洁", "保安", "餐饮",
    "超市", "加油", "危化品", "维修", "停车", "卫生间", "水电", "污水", "环保",
    "客房", "仓库", "问卷", "满意度", "门前三包", "同城同价"
  ];
  for (const kw of keywords) {
    if (name.includes(kw)) return kw;
  }
  return "";
}

function deriveStdRef(fileName, existingStdRef) {
  const existing = String(existingStdRef || "").trim();
  const stdPrefix = '(?:GB(?:[_\\s]?T)?|GBZ|HJ|YY(?:[_\\s]?T)?|WS(?:[_\\s]?T)?|DB\\d*|ISO|IEC|CJJ|JGJ|GA|SB|LY|NY|QC|HG|SL|JTG)';
  const existingLooksValid = (text) => new RegExp(stdPrefix, "i").test(String(text || ""))
    && /\d{2,4}[-.]\d{1,4}/.test(String(text || ""));
  if (existing && !/^\d+$/.test(existing) && existingLooksValid(existing)) {
    return existing;
  }
  const name = String(fileName || "");
  const bracketMatches = [...name.matchAll(/[（(]([^）)]{2,120})[）)]/g)];
  const isRelevant = (text) => {
    const t = String(text || "");
    return new RegExp(stdPrefix, "i").test(t) && /\d{2,4}[-.]\d{1,4}/.test(t);
  };
  for (const match of bracketMatches) {
    const candidate = match[1].trim();
    if (/^\d+$/.test(candidate)) continue;
    if (isRelevant(candidate)) return candidate.replace(/\s+/g, " ").trim();
  }
  const directPatterns = [
    new RegExp(`(${stdPrefix}\\s*[\\w. /-]*\\d{2,4}[-.]\\d{1,4}(?:-\\d{4})?)`, "i"),
    new RegExp(`(${stdPrefix}\\s*\\d{2,4}[-.]\\d{1,4}(?:-\\d{4})?)`, "i"),
  ];
  for (const re of directPatterns) {
    const m = name.match(re);
    if (m && m[1]) {
      const candidate = m[1].replace(/\s+/g, " ").trim();
      if (!/^\d+$/.test(candidate)) return candidate;
    }
  }
  return "";
}

function buildAnalysis(row) {
  const base = typeAnalysis[row.doc_type] || "资料类文件，建议先确认正式版本、适用范围和可引用条款，再决定是否进入知识库主集。";
  const extText = extAnalysis[row.ext] || "";
  return extText ? `${base} ${extText}` : base;
}

function sizeKbText(sizeKb) {
  if (!sizeKb && sizeKb !== 0) return "";
  return Number(sizeKb);
}

function aggregate(rows, keyFn) {
  const map = new Map();
  for (const row of rows) {
    const key = keyFn(row) || "未分类";
    map.set(key, (map.get(key) || 0) + 1);
  }
  return [...map.entries()].sort((a, b) => {
    if (a[0] === b[0]) return 0;
    return a[0].localeCompare(b[0], "zh-Hans-CN");
  });
}

function writeTable(sheet, startRow, startCol, headers, rows) {
  const headerRange = sheet.getRangeByIndexes(startRow, startCol, 1, headers.length);
  headerRange.values = [headers];
  if (rows.length > 0) {
    sheet.getRangeByIndexes(startRow + 1, startCol, rows.length, headers.length).values = rows;
  }
  return { headerRange, dataRange: rows.length > 0 ? sheet.getRangeByIndexes(startRow + 1, startCol, rows.length, headers.length) : null };
}

function styleHeader(range) {
  const fmt = range.format;
  fmt.font.bold = true;
  fmt.font.color = "#1F1F1F";
  fmt.fill.color = "#D9EAF7";
  fmt.horizontalAlignment = "center";
  fmt.verticalAlignment = "middle";
  fmt.wrapText = true;
}

function styleBody(range) {
  const fmt = range.format;
  fmt.verticalAlignment = "top";
  fmt.wrapText = true;
}

async function main() {
  const raw = JSON.parse(await fs.readFile(INPUT_JSON, "utf8"));

  const rows = raw
    .map((row, idx) => {
      const fileName = row.file_name || "";
      const ext = (row.ext || path.extname(fileName).replace(".", "") || "").toLowerCase();
      const folder = row.folder || "";
      const version = row.version || "无显式版本";
      const stdRef = deriveStdRef(fileName, row.std_ref || "");
      const docType = row.doc_type || "未分类";
      const topic = normalizeTopic(row.topic || "", fileName);
      const analysis = buildAnalysis({
        doc_type: docType,
        ext,
      });
      return {
        index: idx + 1,
        folder,
        file_name: fileName,
        ext,
        version,
        std_ref: stdRef,
        doc_type: docType,
        topic,
        analysis,
        size_kb: sizeKbText(row.size_kb),
        path: row.path || "",
      };
    })
    .sort((a, b) => {
      const fa = folderOrder.indexOf(a.folder);
      const fb = folderOrder.indexOf(b.folder);
      if (fa !== fb) return fa - fb;
      return a.file_name.localeCompare(b.file_name, "zh-Hans-CN");
    })
    .map((row, idx) => ({ ...row, index: idx + 1 }));

  const workbook = Workbook.create();

  const wsList = workbook.worksheets.add("文件清单");
  const wsSummary = workbook.worksheets.add("汇总");
  const wsNotes = workbook.worksheets.add("说明");

  // 文件清单
  const listHeaders = [
    "序号",
    "分类目录",
    "文件名",
    "扩展名",
    "版本号",
    "标准号/编号",
    "文档类型",
    "主题关键词",
    "初步分析",
    "文件大小KB",
    "原始路径",
  ];
  const listData = rows.map((r) => [
    r.index,
    r.folder,
    r.file_name,
    r.ext,
    r.version,
    r.std_ref,
    r.doc_type,
    r.topic,
    r.analysis,
    r.size_kb,
    r.path,
  ]);
  const { headerRange: listHeaderRange, dataRange: listDataRange } = writeTable(wsList, 0, 0, listHeaders, listData);
  styleHeader(listHeaderRange);
  if (listDataRange) styleBody(listDataRange);
  wsList.freezePanes.freezeRows(1);
  wsList.showGridLines = true;

  const listWidths = [60, 210, 460, 85, 90, 180, 140, 120, 430, 100, 560];
  listWidths.forEach((w, i) => {
    wsList.getRange(`${colName(i)}:${colName(i)}`).format.columnWidthPx = w;
  });

  // 汇总
  wsSummary.getRange("A1:F1").values = [["知识库原始资料清单汇总"]];
  wsSummary.getRange("A1:F1").merge();
  wsSummary.getRange("A1").format.font.bold = true;
  wsSummary.getRange("A1").format.font.size = 16;

  wsSummary.getRange("A3:B3").values = [["总文件数", rows.length]];
  wsSummary.getRange("D3:E3").values = [["覆盖分类目录数", new Set(rows.map((r) => r.folder)).size]];
  wsSummary.getRange("A5:B5").values = [["说明", "本表仅覆盖 raw/标准化体系_分类版 下 02-07 文件夹，未纳入 01完整原始资料。"]];

  const folderCounts = aggregate(rows, (r) => r.folder);
  const typeCounts = aggregate(rows, (r) => r.doc_type);
  const extCounts = aggregate(rows, (r) => r.ext || "未识别");

  const folderTable = [["分类目录", "数量"], ...folderCounts];
  const typeTable = [["文档类型", "数量"], ...typeCounts];
  const extTable = [["扩展名", "数量"], ...extCounts];

  const folderStartRow = 7;
  const { headerRange: folderHeader } = writeTable(wsSummary, folderStartRow, 0, folderTable[0], folderTable.slice(1));
  styleHeader(folderHeader);
  styleBody(wsSummary.getRangeByIndexes(folderStartRow + 1, 0, folderTable.length - 1, folderTable[0].length));

  const typeStartRow = 7;
  const { headerRange: typeHeader } = writeTable(wsSummary, typeStartRow, 3, typeTable[0], typeTable.slice(1));
  styleHeader(typeHeader);
  styleBody(wsSummary.getRangeByIndexes(typeStartRow + 1, 3, typeTable.length - 1, typeTable[0].length));

  const extStartRow = 7;
  const { headerRange: extHeader } = writeTable(wsSummary, extStartRow, 6, extTable[0], extTable.slice(1));
  styleHeader(extHeader);
  styleBody(wsSummary.getRangeByIndexes(extStartRow + 1, 6, extTable.length - 1, extTable[0].length));

  wsSummary.getRange("A22").values = [["各目录的初步定位"]];
  wsSummary.getRange("A22").format.font.bold = true;
  wsSummary.getRangeByIndexes(22, 0, 6, 2).values = folderOrder.map((folder) => [folder, folderNote[folder] || ""]);
  styleBody(wsSummary.getRangeByIndexes(23, 0, 6, 2));
  wsSummary.getRangeByIndexes(22, 0, 7, 2).format.autofitRows();

  wsSummary.freezePanes.freezeRows(3);
  wsSummary.getRange("A:A").format.columnWidthPx = 230;
  wsSummary.getRange("B:B").format.columnWidthPx = 120;
  wsSummary.getRange("C:C").format.columnWidthPx = 240;
  wsSummary.getRange("D:D").format.columnWidthPx = 220;
  wsSummary.getRange("E:E").format.columnWidthPx = 240;
  wsSummary.getRange("F:F").format.columnWidthPx = 240;
  wsSummary.getRange("G:G").format.columnWidthPx = 120;
  wsSummary.getRange("H:H").format.columnWidthPx = 120;

  // 说明
  const notes = [
    ["字段说明", "说明"],
    ["范围", "仅覆盖 raw/标准化体系_分类版 下的 02-07 文件夹；未纳入 01完整原始资料。"],
    ["版本号", "优先从文件名中的 v1.0 / v1.1 等格式提取；没有显式版本的，统一写为“无显式版本”。"],
    ["标准号/编号", "优先提取文件名中括号或全角括号内的标准号、编号或法规引用。"],
    ["文档类型", "根据文件夹名称和文件名关键词做首轮归类，后续可人工修正。"],
    ["初步分析", "基于文件名、扩展名和文档类型生成的第一轮判断，主要用于知识库预处理和后续抽样复核。"],
    ["文件大小KB", "来源于原始文件统计值，仅作粗略参考。"],
  ];
  wsNotes.getRangeByIndexes(0, 0, notes.length, 2).values = notes;
  styleHeader(wsNotes.getRange("A1:B1"));
  styleBody(wsNotes.getRangeByIndexes(1, 0, notes.length - 1, 2));
  wsNotes.getRange("A:A").format.columnWidthPx = 180;
  wsNotes.getRange("B:B").format.columnWidthPx = 920;
  wsNotes.freezePanes.freezeRows(1);

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await output.save(OUTPUT_FILE);
  console.log(`saved ${OUTPUT_FILE}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
