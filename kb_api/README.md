# kb-api

这是给华为 AgentArts `General` 第三方知识库用的适配服务骨架。

## 接口

- `GET /health`
- `GET /knowledge-bases`
- `POST /knowledge-bases/retrieve`

## 本地运行

```bash
source /Users/chenzhuo/hb/.venv_kb/bin/activate
export KB_ROOT_DIR=/Users/chenzhuo/hb/knowledge_base
export KB_API_KEY=change-me
export KB_RETRIEVAL_MODE=hybrid
uvicorn kb_api.main:app --host 0.0.0.0 --port 8080
```

## Docker 运行

```bash
docker compose -f knowledge_base/kb_api/docker-compose.yml up --build
```

## ECS 对外端口

- `http://<ECS-IP>:9090` -> `nginx`
- `http://<ECS-IP>:9091` -> `kb-api`

## 说明

- 当前实现读取本地 `chunks.jsonl`、`vector_index.sqlite`、关键词矩阵和 embedding 矩阵。
- 默认检索模式是 `hybrid`，按 `KB_KEYWORD_WEIGHT=0.60`、`KB_EMBEDDING_WEIGHT=0.40` 融合关键词分数和 embedding 分数。
- 当前线上索引仍可使用本地 LSA dense fallback；如果用 `embedding-service` 重新建库，`kb-api` 会调用 `KB_EMBEDDING_SERVICE_URL` 生成 query embedding。
- 重新建库可执行：`python /Users/chenzhuo/hb/knowledge_base/scripts/build_hybrid_vectors.py`。
- 中文 embedding 服务说明见：[embedding-service README](/Users/chenzhuo/hb/knowledge_base/embedding_service/README.md)。
