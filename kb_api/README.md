# kb-api

这是给华为 AgentArts `General` 第三方知识库用的适配服务骨架。

## 接口

- `GET /health`
- `GET /` 或 `GET /ui`
- `GET /knowledge-base-manager-ui`
- `GET /pipeline-config-ui`
- `GET /knowledge-bases`
- `POST /knowledge-bases/retrieve`
- `GET /knowledge-base-registry`
- `POST /knowledge-base-registry`
- `PUT /knowledge-base-registry/{knowledge_base_id}`
- `DELETE /knowledge-base-registry/{knowledge_base_id}`
- `GET /pipeline-config`
- `PUT /pipeline-config`
- `GET /raw-files`
- `POST /raw-files/upload`
- `DELETE /raw-files`
- `GET /raw-files/pipeline`
- `POST /raw-files/pipeline`

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

- `http://<ECS-IP>:9090` -> `nginx`，同样也是 WebUI 首页和原始文件管理入口
- `http://<ECS-IP>:9091` -> `kb-api`

## 说明

- 当前实现读取本地 `chunks.jsonl`、`vector_index.sqlite`、关键词矩阵和 embedding 矩阵。
- 默认检索模式是 `hybrid`，按 `KB_KEYWORD_WEIGHT=0.60`、`KB_EMBEDDING_WEIGHT=0.40`，并叠加 `KB_RULE_WEIGHT=0.20` 的业务规则分数。
- 检索策略已支持查询扩展和业务实体强召回，当前重点覆盖危化品车辆、拥堵疏导、违规收银、设备巡检、消防检查等场景。
- 当前推荐索引使用 `bge-small-zh-v1.5` 重新建库；如 embedding 服务不可用，`kb-api` 会自动降级到关键词检索和规则增强。
- `pipeline_config.json` 会保存在 `/data/kb/operations/`，WebUI 的“流程配置”页面会直接读写这份文件。
- `knowledge_bases.json` 会保存在 `/data/kb/operations/`，WebUI 的“知识库管理”页面会直接读写这份文件。
- 重新建库可执行：`python /Users/chenzhuo/hb/knowledge_base/scripts/build_hybrid_vectors.py`。
- 中文 embedding 服务说明见：[embedding-service README](/Users/chenzhuo/hb/knowledge_base/embedding_service/README.md)。
