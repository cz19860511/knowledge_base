# kb-api 部署说明

## 目标

把本地知识库与 RAG 原型部署到阿里云 ECS，作为华为 AgentArts `General` 第三方知识库后端。

## ECS 目录建议

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
  vectors/
  rag/
  selected/
  models/
```

其中 Nginx 配置位于 `/opt/kb-app/kb_api/nginx.conf`，由 `docker-compose.ecs.yml` 挂载到容器内。

## 本地同步到 ECS

### 1. 拷贝环境模板

```bash
cp /opt/kb-app/kb_api/.env.example /opt/kb-app/kb_api/.env
```

### 2. 修改 `.env`

- `KB_API_KEY`
- `KB_BATCH_ID`
- `KB_KB_ID`
- `KB_PORT`
- `KB_RETRIEVAL_MODE=hybrid`
- `KB_KEYWORD_WEIGHT=0.60`
- `KB_EMBEDDING_WEIGHT=0.40`
- `KB_RULE_WEIGHT=0.20`
- `KB_QUERY_EXPANSION_ENABLED=true`
- `KB_EMBEDDING_SERVICE_URL=http://embedding-service:9100`

### 3. 同步代码和数据

```bash
bash kb_api/deploy_ecs.sh root 1.2.3.4 /opt/kb-app /data/kb
```

当前生产批次还需要同步：

```text
/data/kb/chunks/batch_20260521/
/data/kb/selected/batch_20260521/
/data/kb/vectors/batch_20260521/
/data/kb/rag/batch_20260521/
/data/kb/models/bge-small-zh-v1.5/
```

### 4. ECS 上启动

```bash
cd /opt/kb-app/kb_api
docker compose -f docker-compose.ecs.yml --profile embedding up -d --build
```

服务端口：

| 服务 | 端口 | 说明 |
|---|---:|---|
| `nginx` | `9090` | 对外入口，AgentArts 优先使用 |
| `kb-api` | `9091` | 直连调试入口 |
| `embedding-service` | `9100` | bge-small embedding 服务 |

`http://<ECS-IP>:9090/` 现在同时承载知识平台 WebUI 首页和原始文件管理页。

### 4.1 如果要启用 HTTPS

- 先把域名解析到 ECS 公网 IP。
- 把证书文件挂到 `/etc/nginx/certs/`。
- 在 `nginx.conf` 里打开 443 server 块。
- 让 AgentArts 连接 `https://你的域名`。

### 5. 验证

```bash
curl http://127.0.0.1:9100/health
curl http://127.0.0.1:9091/health
curl http://127.0.0.1:9090/health
curl http://8.161.227.173:9090/health
curl -H "Authorization: Bearer change-me" http://127.0.0.1:9091/knowledge-bases
curl -H "Authorization: Bearer change-me" http://127.0.0.1:9091/raw-files
curl -H "Authorization: Bearer change-me" http://127.0.0.1:9091/raw-files/pipeline
```

embedding 实测：

```bash
curl -X POST http://127.0.0.1:9100/embed \
  -H 'Content-Type: application/json' \
  -d '{"texts":["test"],"normalize":true,"input_type":"query"}'
```

检索实测：

```bash
curl -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <KB_API_KEY>' \
  -d '{"knowledge_base_ids":["ai_qna_standard_v1"],"query":"服务区危化品车辆现场处理流程是什么","top_k":3,"limit":3,"search_threshold":0.0}'
```

期望返回：

- `retrieval_mode` 为 `hybrid`
- `matched_rules` 包含 `hazmat_vehicle`
- 返回内容可追溯到 chunk、章节和来源文件

## 对外访问

- `9090`：Nginx 入口
- `9091`：kb-api 直连入口
- `9100`：embedding-service，生产联调时不建议对 AgentArts 暴露

## 注意事项

- AgentArts 调用时，ECS 服务必须能被公网访问。
- `KB_API_KEY` 不要写死在代码里。
- 当前 embedding 镜像使用 CPU-only PyTorch，避免默认拉 CUDA 依赖。
- 数据目录同步后，尽量不要直接在 ECS 上手工改 chunk 或 vector 文件。
- 首次联调先用 HTTP 跑通，再切 HTTPS。
