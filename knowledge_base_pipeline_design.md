# 开源知识库文档处理流水线设计方案

## 1. 方案目标

本方案用于搭建一个可私有化、可扩展、可接入华为 AgentArts 平台的企业级知识库处理流水线。

核心目标不是简单地把 PDF、Word、Excel 等文件直接导入知识库，而是先通过多种文档解析工具进行预处理和质量对比，再将处理后的 Markdown 文件分别进入两个路径：

1. **路径 A：向量化入库**  
   用于 RAG 检索、问答、引用溯源。

2. **路径 B：LLM Kimi 二次处理**  
   用于结构修复、摘要生成、条款抽取、知识标签、问答对生成等。

最终形成一个可供华为 AgentArts、OpenClaw、项目管理 Agent、需求管理 Agent 等调用的统一知识库服务。

---

## 2. 总体架构

```text
原始文件 PDF / Word / Excel / PPT / 图片
        ↓
文档预处理调度器
        ↓
┌──────────────┬──────────────┬──────────────┐
│   MinerU     │   Marker     │  MarkItDown  │
└──────────────┴──────────────┴──────────────┘
        ↓
三份 Markdown / JSON / 图片 / 表格结果
        ↓
解析质量评估器
        ↓
选择最佳版本 / 合并增强版本
        ↓
标准化 Markdown
        ↓
┌────────────────────────────┬────────────────────────────┐
│ 路径 A：向量化入库          │ 路径 B：Kimi 二次处理         │
│ 用于 RAG 检索               │ 用于结构化、摘要、标签、问答   │
└────────────────────────────┴────────────────────────────┘
        ↓
统一知识库服务
        ↓
AgentArts / OpenClaw / 项目管理 Agent / 需求管理 Agent
```

---

## 3. 三个预处理工具的定位

### 3.1 MinerU

MinerU 适合处理：

```text
中文 PDF
扫描件 PDF
复杂版式 PDF
论文、合同、技术规格书
带表格、图片、公式、页眉页脚的文档
```

建议定位：**复杂 PDF 主力解析器**。

适用场景包括：

- 合同文件
- 技术规格书
- 施工方案
- 设计说明
- 扫描版资料
- 含复杂表格和多栏版式的 PDF

---

### 3.2 Marker

Marker 适合处理：

```text
PDF
图片
PPTX
DOCX
XLSX
HTML
EPUB
英文/中英文混排材料
表格、公式、代码块较多的技术文档
```

建议定位：**多格式文档解析器 + 技术文档解析器**。

适用场景包括：

- 技术文档
- 产品说明书
- 开发文档
- PPT 转知识库
- Word 转 Markdown
- Excel 内容抽取
- 中英文混排资料

---

### 3.3 MarkItDown

MarkItDown 适合处理：

```text
Office 文档
普通 PDF
网页
轻量级 Markdown 转换
快速批量转换
非复杂版式资料
```

建议定位：**轻量快速转换器 / 兜底解析器**。

适用场景包括：

- 普通 Word 文档
- 简单 PDF
- 网页资料
- 快速批量导入
- 文档结构较简单的资料

---

## 4. 第一阶段：三解析器并行预处理

每个原始文档进入系统后，同时跑三条解析链路。

示例：

```text
input/主合同.pdf
   ├── mineru/output/主合同.md
   ├── marker/output/主合同.md
   └── markitdown/output/主合同.md
```

系统需要保留中间产物，便于后续质量评估、人工抽查和问题追溯。

建议目录结构：

```text
documents/
  raw/
    主合同.pdf

  parsed/
    主合同/
      mineru/
        content.md
        layout.json
        images/
        tables/
        score.json

      marker/
        content.md
        metadata.json
        images/
        score.json

      markitdown/
        content.md
        metadata.json
        score.json

  selected/
    主合同.md

  refined/
    主合同.refined.md
    主合同.summary.md
    主合同.qa.json
    主合同.tags.json
```

---

## 5. 第二阶段：解析质量评估

文档解析不能只看“是否生成 Markdown”，而要看生成结果是否适合后续知识库检索、引用和二次分析。

建议从以下维度进行评分。

| 指标 | 说明 |
|---|---|
| 标题层级完整度 | 是否保留章、节、条款结构 |
| 页码保留情况 | 是否能追溯到原文页码 |
| 表格还原质量 | 清单、参数表、合同表格是否完整 |
| 图片/图注提取 | 是否保留图片引用和说明 |
| 文本顺序 | 多栏、页眉页脚、脚注是否错乱 |
| OCR 准确率 | 扫描件是否识别准确 |
| 噪声比例 | 是否有页眉、页脚、乱码、重复文本 |
| Markdown 可读性 | 是否适合后续切片 |
| 结构化程度 | 是否能识别标题、列表、表格、条款 |
| LLM 可处理性 | 是否适合送入 Kimi 做二次处理 |

每个解析结果建议生成一个评分文件。

示例：

```json
{
  "parser": "mineru",
  "document": "主合同.pdf",
  "score": 86,
  "title_score": 90,
  "table_score": 82,
  "ocr_score": 88,
  "noise_score": 75,
  "page_reference_score": 90,
  "recommendation": "selected",
  "reason": "标题结构完整，表格基本可用，适合合同类文档入库"
}
```

---

## 6. 第三阶段：最佳版本选择策略

### 6.1 默认选择规则

```text
复杂 PDF / 扫描件 / 合同 / 技术规格书：
优先 MinerU

多格式文档 / 表格公式较多 / 技术资料：
优先 Marker

普通 Office / 简单文档 / 快速批量导入：
优先 MarkItDown
```

### 6.2 动态评分选择

最终不建议写死某一个解析器，而是根据评分动态选择。

示例逻辑：

```python
best = max(
    [mineru_result, marker_result, markitdown_result],
    key=lambda x: x.score
)
```

### 6.3 合并增强策略

如果多个解析器各有优势，可以合并生成增强版 Markdown。

示例：

```text
MinerU：正文结构更好
Marker：表格更好
MarkItDown：普通段落更干净

最终 selected.md = MinerU 正文 + Marker 表格 + MarkItDown 元数据补充
```

这种方式适合处理复杂合同、技术规格书、清单文件等资料。

---

# 7. 双路径处理设计

## 7.1 路径 A：向量化入库

路径 A 的目标是：

```text
让 Agent 能快速、准确、可追溯地检索知识
```

处理流程：

```text
selected.md
   ↓
Markdown 清洗
   ↓
按标题 / 条款 / 表格 / 语义切片
   ↓
生成 chunk
   ↓
Embedding
   ↓
向量库
   ↓
RAG 检索服务
```

---

### 7.1.1 向量化前的 Markdown 标准

建议统一成如下格式：

```md
# 文档名称：吴圩机场站前综合体机电工程主合同

## 元数据

- 文件名：01-吴圩机场-站前综合体机电工程-主合同.pdf
- 文档类型：主合同
- 专业：机电工程
- 来源：合同文件
- 解析器：MinerU
- 页码范围：1-120

## 第 1 章 合同协议书

<!-- page: 1 -->

### 1.1 工程概况

正文内容……

<!-- page: 2 -->

### 1.2 承包范围

正文内容……
```

---

### 7.1.2 切片策略

不要简单按固定字数切片，例如每 500 字硬切一次。应根据文档类型采用不同切片策略。

#### 合同类文档

```text
一级：章节
二级：条款
三级：自然段
保留：条款号、页码、合同附件来源
```

#### 技术规格书类文档

```text
一级：专业
二级：系统
三级：设备/材料/施工要求/验收要求
保留：系统名称、专业、页码
```

#### 清单类 / Excel 类文档

```text
一级：清单章节
二级：清单项
三级：项目特征、计量单位、工程量、备注
保留：清单编码、项目名称、专业
```

---

### 7.1.3 Chunk 数据结构

建议每个 chunk 至少保留以下信息。

```json
{
  "chunk_id": "contract_001_00023",
  "doc_id": "contract_001",
  "doc_name": "主合同.pdf",
  "doc_type": "主合同",
  "major": "机电",
  "section": "承包范围",
  "clause_no": "2.1.3",
  "page": 35,
  "text": "……",
  "metadata": {
    "parser": "mineru",
    "source_md": "selected/主合同.md",
    "version": "v1"
  }
}
```

---

## 7.2 路径 B：Kimi 二次处理

路径 B 的目标不是直接检索，而是生成更高质量的知识结构。

Kimi 适合处理：

```text
长文档二次整理
合同条款结构化
技术要求抽取
自动摘要
知识标签
问答对生成
风险点提取
结算争议点提取
```

处理流程：

```text
selected.md
   ↓
Kimi 文档结构修复
   ↓
refined.md
   ↓
摘要生成 summary.md
   ↓
条款抽取 clauses.json
   ↓
标签生成 tags.json
   ↓
问答对生成 qa.json
   ↓
进入结构化知识库 / 测试集 / Agent 工具调用
```

---

# 8. Kimi 二次处理内容设计

## 8.1 文档结构修复

输入：

```text
selected.md
```

输出：

```text
refined.md
```

处理目标：

```text
修复标题层级
删除重复页眉页脚
补全条款结构
统一表格格式
保留页码标记
修复明显 OCR 错字
```

注意：Kimi 不应该随意改写原文。提示词中必须明确限制。

建议提示词：

```text
你是一个企业知识库文档结构化助手。

你的任务是对输入的 Markdown 文档进行结构整理。

要求：
1. 只能做结构整理、格式规范和明显 OCR 错误修复。
2. 不得改变合同条款、技术要求、工程范围的原意。
3. 不得新增原文不存在的要求。
4. 所有不确定内容必须标记为【疑似 OCR 错误】。
5. 必须保留页码标记，例如 <!-- page: 12 -->。
6. 必须保留原文中的条款编号、章节编号、表格内容。
7. 对明显重复的页眉页脚可以删除。
8. 输出格式必须是 Markdown。
```

---

## 8.2 生成文档摘要

输出：

```text
summary.md
```

建议摘要结构：

```md
# 文档摘要

## 文档类型
主合同

## 核心内容
……

## 涉及专业

- 电气
- 暖通
- 给排水
- 消防
- 智能化

## 对结算有影响的内容
……

## 对施工单位有风险的内容
……

## 与其他文件可能冲突的内容
……
```

---

## 8.3 生成结构化条款

输出：

```text
clauses.json
```

示例结构：

```json
{
  "document": "主合同.pdf",
  "clauses": [
    {
      "clause_id": "2.1.3",
      "title": "承包范围",
      "page": 35,
      "original_text": "……",
      "normalized_text": "……",
      "clause_type": "scope",
      "related_major": ["电气", "暖通", "给排水"],
      "risk_level": "high",
      "settlement_impact": true
    }
  ]
}
```

该数据可用于：

- 合同风险分析
- 对外结算争议点分析
- 清单漏项分析
- 项目特征不准确分析
- 合同范围与技术规格书对比

---

## 8.4 自动生成知识标签

输出：

```text
tags.json
```

示例：

```json
{
  "tags": [
    "主合同",
    "承包范围",
    "机电安装",
    "电气",
    "暖通",
    "给排水",
    "结算依据",
    "清单漏项",
    "项目特征",
    "风险条款"
  ]
}
```

标签可用于：

- 文档分类
- 知识库筛选
- Agent 工具路由
- 专题知识库构建
- 后续知识图谱建设

---

## 8.5 自动生成问答对

输出：

```text
qa.json
```

示例：

```json
[
  {
    "question": "本项目机电工程的承包范围包括哪些内容？",
    "answer": "……",
    "source": {
      "document": "主合同.pdf",
      "page": 35,
      "clause": "2.1.3"
    }
  },
  {
    "question": "哪些内容可能影响对外结算？",
    "answer": "……",
    "source": {
      "document": "主合同.pdf",
      "page": 42
    }
  }
]
```

这些 QA 数据可用于：

```text
知识库增强
Agent 测试集
RAG 评估集
自动回归测试
常见问题库
```

---

# 9. 最终入库策略

最终知识库不建议只存一种内容，而是存三类内容。

## 9.1 原文向量库

来源：

```text
selected.md / refined.md
```

用途：

```text
精准检索
原文引用
问答溯源
```

---

## 9.2 结构化知识库

来源：

```text
clauses.json
tags.json
summary.md
```

用途：

```text
筛选
分类
知识图谱
风险分析
结算分析
规则判断
```

---

## 9.3 QA 测试库

来源：

```text
qa.json
```

用途：

```text
测试 Agent 回答质量
测试 RAG 命中率
测试不同解析器效果
沉淀业务常见问题
```

---

# 10. 与华为 AgentArts 的集成关系

建议不要让 AgentArts 直接管理所有知识库底层细节，而是采用如下架构：

```text
RAGFlow / 自建知识库
        ↓
知识库 API
        ↓
AgentArts 插件 / 工具 / MCP
        ↓
业务 Agent
```

AgentArts 负责：

```text
流程编排
智能体任务分解
调用知识库工具
调用 Kimi 二次分析能力
调用项目管理系统
调用飞书
```

自建知识库负责：

```text
文档解析
文档清洗
向量检索
引用溯源
结构化知识沉淀
```

---

## 10.1 AgentArts 可调用的知识库 API

建议封装一个统一知识库服务，例如：

```text
kb-query-service
```

提供接口：

```http
POST /kb/search
POST /kb/ask
POST /kb/retrieve
POST /kb/documents/upload
POST /kb/documents/sync
```

示例请求：

```http
POST /api/kb/search
```

请求体：

```json
{
  "query": "给排水技术规格书中对阀门有什么要求？",
  "top_k": 8,
  "dataset": "wuxu_airport_mep"
}
```

返回体：

```json
{
  "results": [
    {
      "content": "……",
      "document": "给排水技术要求.pdf",
      "page": 18,
      "score": 0.91
    }
  ]
}
```

---

# 11. MVP 版本设计

第一版不要做太复杂，先做一个本地可跑通版本。

## 11.1 MVP 流程

```text
1. 上传一个 PDF
2. MinerU / Marker / MarkItDown 同时解析
3. 生成三份 Markdown
4. 人工查看对比
5. 选择最佳 Markdown
6. 进入向量库
7. 同时送 Kimi 做二次整理
8. 生成 refined.md / summary.md / qa.json / tags.json
9. AgentArts 通过 API 查询知识库
```

---

## 11.2 MVP 目录结构

```text
knowledge-base-pipeline/
  docker-compose.yml

  data/
    raw/
    parsed/
    selected/
    refined/
    embeddings/
    evaluation/

  services/
    parser-service/
      mineru_runner.py
      marker_runner.py
      markitdown_runner.py

    evaluator-service/
      evaluate_markdown.py
      compare_results.py

    kimi-service/
      refine_markdown.py
      extract_clauses.py
      generate_summary.py
      generate_qa.py

    vector-service/
      chunker.py
      embedder.py
      retriever.py

    api-service/
      main.py
      routes/
        upload.py
        parse.py
        search.py
        ask.py
```

---

# 12. 推荐技术栈

## 12.1 文档解析

```text
MinerU
Marker
MarkItDown
```

## 12.2 后端服务

```text
Python
FastAPI
```

## 12.3 任务队列

```text
Celery
RQ
```

## 12.4 文件与对象存储

```text
MinIO
本地文件系统
```

## 12.5 数据库

```text
PostgreSQL
MySQL
```

## 12.6 向量库

```text
Milvus
Qdrant
Elasticsearch
RAGFlow 内置方案
```

## 12.7 LLM

```text
Kimi API
Qwen
DeepSeek
华为云盘古模型
```

## 12.8 Embedding 模型

```text
bge-m3
bge-large-zh
m3e
华为云 Embedding
text-embedding 类模型
```

## 12.9 知识库平台

```text
RAGFlow
```

## 12.10 Agent 平台

```text
华为 AgentArts
OpenClaw
```

---

# 13. 核心亮点

本方案的核心亮点是：

```text
不是直接文档入库，
而是先做“文档解析质量竞争”。
```

也就是：

```text
同一份文档
   ↓
多解析器并行处理
   ↓
质量评估
   ↓
最佳 Markdown / 合并增强 Markdown
   ↓
双路径处理
   ↓
知识库入库
   ↓
Agent 调用
```

这种设计可以有效解决企业知识库中最常见的问题：

```text
PDF 解析错
表格乱
页码丢失
合同条款断裂
向量检索命中但答案不准
LLM 总结时引用不到原文
知识库后期难维护
```

---

# 14. 后续演进方向

## 14.1 自动质量评分

后续可以增加自动质量评分模型，对三种解析结果进行自动比较。

评分依据包括：

- 标题结构完整度
- 表格可读性
- 页码追溯能力
- 文本重复率
- OCR 错误率
- 与原文版式一致性
- 后续 RAG 命中效果

---

## 14.2 人工审核工作台

可建设一个简单前端页面，用于人工对比三种解析结果。

功能包括：

- 左侧原文 PDF
- 右侧三种 Markdown 对比
- 显示评分
- 人工选择最佳版本
- 人工标记错误段落
- 一键进入向量化 / Kimi 二次处理

---

## 14.3 文档类型识别

系统可先判断文档类型，再决定解析策略。

示例：

```text
合同类：MinerU 优先
技术规格书：MinerU + Marker 对比
Office 文档：MarkItDown 优先
Excel 清单：Marker / 自定义 Excel 解析优先
扫描件：MinerU OCR 优先
```

---

## 14.4 与飞书资料同步

后续可增加飞书同步能力：

```text
飞书文档 / 飞书表格 / 飞书知识库
        ↓
导出为 docx / xlsx / pdf / markdown
        ↓
进入文档预处理流水线
        ↓
统一知识库
        ↓
AgentArts / OpenClaw 调用
```

这与你后续想做的飞书需求管理 Agent 可以很好结合。

---

# 15. 最终建议

建议将该方案作为你的知识库平台第一版技术路线。

最小可落地版本可以先实现：

```text
RAGFlow
+ MinerU
+ Marker
+ MarkItDown
+ Kimi API
+ FastAPI 知识库服务
+ AgentArts API / 插件对接
```

第一阶段重点不是功能做大，而是先打通：

```text
文档上传
三解析器预处理
解析结果对比
最佳 Markdown 选择
向量化入库
Kimi 二次处理
AgentArts 查询
```

只要这条链路跑通，后续就可以逐步扩展成完整的：

```text
文档解析中台
知识入库中台
RAG 检索中台
AgentArts 工具服务
企业知识资产管理系统
```
