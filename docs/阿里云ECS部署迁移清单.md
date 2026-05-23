# 阿里云 ECS 部署迁移清单

目标：把当前本地知识库与 RAG 原型快速迁移到阿里云 ECS，作为 AgentArts `General` 第三方知识库的后端服务。

当前部署状态：

| 项目 | 值 |
|---|---|
| ECS 公网 IP | `8.161.227.173` |
| 对外入口 | `http://8.161.227.173:9090` |
| kb-api 直连端口 | `9091` |
| embedding-service 端口 | `9100` |
| 当前批次 | `batch_20260521` |
| 当前模型 | `bge-small-zh-v1.5` |
| 当前检索方案 | `keyword + bge-small embedding + rules` |
| 当前验证状态 | `/health`、`/embed`、`/knowledge-bases/retrieve` 均已通过 |

## 1. 迁移原则

- 本地继续保留研发环境，ECS 作为稳定运行环境。
- ECS 只部署“可对外提供接口”的服务，不保留开发时的杂项产物。
- 大文件、静态索引和版本数据分层存放，便于后续增量更新。
- 先跑通最小闭环，再补运维、监控、灰度和自动更新。

## 2. 需要迁移的内容

### 2.1 必须迁移

- `knowledge_base/scripts/`
- `knowledge_base/chunks/batch_20260521/`
- `knowledge_base/selected/batch_20260521/`
- `knowledge_base/vectors/batch_20260521/`
- `knowledge_base/rag/batch_20260521/`
- `knowledge_base/docs/目录说明.md`
- `knowledge_base/docs/阿里云ECS部署迁移清单.md`

### 2.2 视情况迁移

- `knowledge_base/raw/`
  - 如果 ECS 需要保留原始资料归档，可同步。
  - 如果只是提供检索服务，可不迁移，仅保留索引和切片。
- `knowledge_base/working/`
  - 只在需要追查解析问题时同步部分批次。
- `knowledge_base/outputs/`
  - 只保留必要的交付预览文件，不作为运行依赖。

### 2.3 不建议迁移

- 本地虚拟环境目录
- 临时实验目录
- `.DS_Store`、缓存、烟测批次
- 非当前批次的旧 smoke / test 产物

## 3. ECS 上的目录结构

建议统一放在：

```text
/opt/kb-app/
  kb_api/
  embedding_service/
  scripts/
  docs/
  requirements-kb-api.txt
  requirements-embedding-service.txt

/data/kb/
  chunks/
  selected/
  vectors/
  rag/
  models/
  logs/
  config/
```

建议映射：

- `/data/kb/chunks/` -> `chunks/batch_20260521`
- `/data/kb/selected/` -> `selected/batch_20260521`
- `/data/kb/vectors/` -> `vectors/batch_20260521`
- `/data/kb/rag/` -> `rag/batch_20260521`
- `/data/kb/models/bge-small-zh-v1.5/` -> 本地 `models/bge-small-zh-v1.5`

## 4. 迁移方式建议

### 4.1 代码

优先用 `git`。

- 本地整理成一个独立仓库。
- ECS 上 `git clone` 后直接部署。
- 后续只拉代码差异，不重复传大文件。

### 4.2 大文件

优先用 `rsync`，必要时先上传 `OSS`。

- 目录体积不大、需要频繁增量更新：`rsync`
- 目录体积大、需要长期归档：`OSS`

推荐顺序：

1. 首次全量：`rsync`
2. 后续增量：`rsync`
3. 归档备份：`OSS`

## 5. ECS 上要起的服务

第一版实际起 3 个服务：

1. `embedding-service`
   - 端口：`9100`
   - 模型：`/data/kb/models/bge-small-zh-v1.5`
   - 设备：CPU
   - 作用：为建库和查询提供中文 embedding
   - 镜像注意：使用 CPU-only PyTorch，避免拉取 CUDA 依赖

2. `kb-api`
   - 端口：`9091 -> 8080`
   - 提供 AgentArts 需要的 `General` 接口
   - 负责知识库列表、检索、返回 chunk 和来源信息
   - 当前检索：关键词、embedding、规则增强融合

3. `nginx`
   - 端口：`9090 -> 80`
   - 对外统一入口
   - 做 HTTPS、反向代理、限流

运行依赖数据：

- `chunks/batch_20260521/chunks.jsonl`
- `vectors/batch_20260521/vector_index.sqlite`
- `vectors/batch_20260521/keyword_matrix.npz`
- `vectors/batch_20260521/embedding_matrix.npy`
- `vectors/batch_20260521/embedding_model.joblib`
- `models/bge-small-zh-v1.5/`

## 6. 部署顺序

### 第 1 步：冻结本地版本

- 确认当前 `batch_20260521` 为正式版。
- 不再频繁修改 `chunks.jsonl` 和 `vector_index.sqlite`。
- 如果要改，先改本地，再重新同步整批。

### 第 2 步：打包代码和数据

- 代码归档为一个压缩包或 git 仓库。
- 数据目录按 `chunks / selected / vectors / rag` 分包。
- 保留版本号和批次号。

### 第 3 步：上传到 ECS

- 代码先到 `/opt/kb-app/`
- 数据到 `/data/kb/`
- 先上传核心索引和模型，再上传次要材料

### 第 4 步：ECS 上验证

- 检查 `vector_index.sqlite` 是否可读
- 检查 `embedding_matrix.npy` 是否为 `3053 x 512`
- 检查 `embedding_model.joblib` 是否为 `bge-small-zh-v1.5`
- 检查 `embedding-service` 是否返回 512 维向量
- 检查 `kb-api` 检索是否返回 `hybrid` 和命中的业务规则

### 第 5 步：封装对外接口

- 实现 AgentArts `General` 知识库需要的接口
- 加 API Key 校验
- 加日志和错误处理

### 第 6 步：联调 AgentArts

- 先做知识库连接测试
- 再做命中测试
- 最后挂到智能体里

## 7. 快速打包清单

### 7.1 代码包

- `knowledge_base/scripts/build_selected_and_chunks.py`
- `knowledge_base/scripts/build_vectors.py`
- `knowledge_base/scripts/search_vectors.py`
- `knowledge_base/scripts/rag_answer.py`
- `knowledge_base/docs/目录说明.md`

### 7.2 数据包

- `knowledge_base/chunks/batch_20260521/`
- `knowledge_base/selected/batch_20260521/`
- `knowledge_base/vectors/batch_20260521/`
- `knowledge_base/rag/batch_20260521/`

### 7.3 配置包

- `kb-api` 配置文件
- `docker-compose.yml`
- `nginx.conf`
- `requirements.txt`

## 8. ECS 启动与验证命令

### 8.1 启动服务

```bash
cd /opt/kb-app/kb_api
docker compose -f docker-compose.ecs.yml --profile embedding up -d --build
```

### 8.2 查看容器

```bash
docker compose -f /opt/kb-app/kb_api/docker-compose.ecs.yml -p kb_api ps
```

应看到：

- `kb_api-embedding-service-1`
- `kb_api-kb-api-1`
- `kb_api-nginx-1`

### 8.3 健康检查

```bash
curl http://127.0.0.1:9100/health
curl http://127.0.0.1:9091/health
curl http://127.0.0.1:9090/health
curl http://8.161.227.173:9090/health
```

### 8.4 embedding 实测

```bash
curl -X POST http://127.0.0.1:9100/embed \
  -H 'Content-Type: application/json' \
  -d '{"texts":["test"],"normalize":true,"input_type":"query"}'
```

期望结果：

- `model` 为 `bge-small-zh-v1.5`
- `dimension` 为 `512`
- `input_type` 为 `query`
- `pooling` 为 `cls`

### 8.5 检索实测

```bash
curl -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <KB_API_KEY>' \
  -d '{"knowledge_base_ids":["ai_qna_standard_v1"],"query":"服务区危化品车辆现场处理流程是什么","top_k":3,"limit":3,"search_threshold":0.0}'
```

期望结果：

- `total` 大于 `0`
- `retrieval_mode` 为 `hybrid`
- `matched_rules` 包含 `hazmat_vehicle`

## 9. 建议的上线检查项

- 服务启动是否成功
- 检索接口是否能返回 top_k
- 是否能返回 chunk 原文和来源路径
- 是否能稳定处理空 query、短 query、无命中 query
- 是否能按知识库 ID 区分结果
- 是否有访问日志
- 是否有错误日志

## 10. 下一步建议

1. 将 AgentArts 第三方知识库地址配置为 `http://8.161.227.173:9090`。
2. 使用实际 `KB_API_KEY` 做连接测试。
3. 正式联调前启用 HTTPS，减少公网 HTTP 暴露风险。
4. 增加访问日志、错误日志和基础监控。
5. 将每次发布的 `batch_id`、模型、索引 manifest 和验证结果归档。
