# knowledge_base

知识平台工程仓库，用于支撑 AI+智能问答智能体的知识库建设、hybrid 检索服务和华为 AgentArts `General` 知识库接口对接。

当前主线能力：

- 原始资料预处理：以 MinerU 为主，Marker/MarkItDown 作为补充。
- Chunk 生成：从确认后的 `selected.md` 生成可入库切片。
- Hybrid 检索：关键词 TF-IDF + dense embedding 融合。
- 检索策略增强：查询扩展、业务实体强召回、规则加权。
- API 服务：`kb-api` 对外适配 AgentArts `General` 接口。
- `9090` 同时作为知识平台 WebUI 首页，可直接查看状态、原始文件管理和检索结果。
- 独立 embedding 服务：`embedding_service` 支持中文 embedding 模型独立部署。

## 仓库结构

```text
knowledge_base/
├── docs/                    # 方案、规范、部署说明
├── embedding_service/       # 独立 embedding 服务
├── kb_api/                  # AgentArts General 适配 API
├── scripts/                 # 预处理、chunk、建库、检索脚本
├── requirements-*.txt       # 服务依赖
├── raw/                     # 原始资料，本地/服务器保存，不进 Git
├── working/                 # 预处理过程产物，不进 Git
├── selected/                # 人工确认后的入库文档，不进 Git
├── chunks/                  # chunk 产物，不进 Git
├── vectors/                 # 向量库产物，不进 Git
└── outputs/                 # 报表、预览和临时输出，不进 Git
```

更详细的目录边界见：[仓库结构与协作规范](docs/仓库结构与协作规范.md)。

## 本地环境

```bash
source /Users/chenzhuo/hb/.venv_kb/bin/activate
```

如果在新机器上部署，先安装两个服务依赖：

```bash
pip install -r requirements-kb-api.txt
pip install -r requirements-embedding-service.txt
```

## 建库流程

1. 原始资料放入 `raw/`。
2. 执行预处理，生成 `working/parsed/` 和评估结果。
3. 从确认后的文档生成 `selected/` 和 `chunks/`。
4. 构建 hybrid 索引，生成 `vectors/`。
5. 启动 `kb-api`，供 AgentArts 调用。

常用命令：

```bash
python scripts/build_selected_and_chunks.py
python scripts/build_hybrid_vectors.py
python scripts/search_hybrid_vectors.py "安全生产责任制的主要要求是什么" --topk 3
```

如需使用独立中文 embedding 服务建库：

```bash
python scripts/build_hybrid_vectors.py \
  --embedding-provider service \
  --embedding-service-url http://127.0.0.1:9100 \
  --embedding-batch-size 16
```

## 启动服务

本地启动 `kb-api`：

```bash
export KB_ROOT_DIR=/Users/chenzhuo/hb/knowledge_base
export KB_API_KEY=change-me
uvicorn kb_api.main:app --host 0.0.0.0 --port 9091
```

本地启动 embedding mock 服务，用于验证链路：

```bash
export KB_EMBEDDING_PROVIDER=mock
export KB_EMBEDDING_MODEL_NAME=mock-zh-384
uvicorn embedding_service.main:app --host 0.0.0.0 --port 9100
```

生产环境建议把中文模型放到：

```text
/data/kb/models/bge-small-zh-v1.5
```

然后通过 `docker compose --profile embedding` 启动 embedding 服务。

## Git 管理原则

进入 Git 的内容：

- 代码：`kb_api/`、`embedding_service/`、`scripts/`
- 工程文档：`docs/`、`README.md`
- 依赖和部署配置：`requirements-*.txt`、`Dockerfile`、`docker-compose*.yml`

不进入 Git 的内容：

- 原始资料：`raw/`
- 中间产物：`working/`、`selected/`、`chunks/`
- 向量库和模型：`vectors/`、`models/`
- 报表和临时输出：`outputs/`、`tmp/`

这些目录建议保存在本地、ECS `/data/kb`、对象存储、Git LFS 或 DVC 中。
