# scripts

知识平台常用脚本目录。

## 资料处理

- `preprocess_raw_02_07.py`：对 `raw/标准化体系_分类版/02-07` 做预处理。
- `build_raw_inventory_excel.mjs`：生成原始资料盘点 Excel。
- `build_selected_and_chunks.py`：基于确认后的资料生成 `selected/` 和 `chunks/`。
- `build_chunk_preview_workbook.mjs`：生成 chunk 预览 Excel。

## 建库与检索

- `build_hybrid_vectors.py`：构建 keyword + embedding hybrid 检索索引。
- `search_hybrid_vectors.py`：本地 hybrid 检索验证。
- `build_vectors.py`：历史 TF-IDF 建库脚本，保留用于兼容或回退。
- `search_vectors.py`：历史 TF-IDF 检索脚本，保留用于兼容或回退。
- `rag_answer.py`：本地 RAG 回答验证脚本。

## 常用命令

```bash
source /Users/chenzhuo/hb/.venv_kb/bin/activate

python scripts/build_selected_and_chunks.py
python scripts/build_hybrid_vectors.py
python scripts/search_hybrid_vectors.py "安全生产责任制的主要要求是什么" --topk 3
```

接入独立 embedding 服务后：

```bash
python scripts/build_hybrid_vectors.py \
  --embedding-provider service \
  --embedding-service-url http://127.0.0.1:9100 \
  --embedding-batch-size 16
```
