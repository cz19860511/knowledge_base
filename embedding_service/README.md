# embedding-service

独立中文 embedding 服务，供两类流程调用：

- 建库阶段：`build_hybrid_vectors.py --embedding-provider service` 批量生成文档向量。
- 查询阶段：`kb-api` 调用 `/embed` 生成 query 向量，再做 hybrid 检索。

## 推荐模型

首版建议使用 `BAAI/bge-small-zh-v1.5`，原因是中文效果稳定、CPU 成本相对可控。后续如果服务器资源允许，可升级到 `BAAI/bge-base-zh-v1.5` 或多语种 `BAAI/bge-m3`。

生产部署建议把模型文件放到：

```bash
/data/kb/models/bge-small-zh-v1.5
```

## 本地启动

```bash
source /Users/chenzhuo/hb/.venv_kb/bin/activate
export KB_EMBEDDING_PROVIDER=transformers
export KB_EMBEDDING_MODEL_PATH=/data/kb/models/bge-small-zh-v1.5
export KB_EMBEDDING_MODEL_NAME=bge-small-zh-v1.5
uvicorn embedding_service.main:app --host 0.0.0.0 --port 9100
```

如果只是验证链路，可用 mock provider：

```bash
export KB_EMBEDDING_PROVIDER=mock
uvicorn embedding_service.main:app --host 0.0.0.0 --port 9100
```

## 测试

```bash
curl http://127.0.0.1:9100/health

curl -X POST http://127.0.0.1:9100/embed \
  -H 'Content-Type: application/json' \
  -d '{"texts":["安全生产责任制的主要要求是什么"],"normalize":true}'
```

## 建库接入

```bash
source /Users/chenzhuo/hb/.venv_kb/bin/activate
python /Users/chenzhuo/hb/knowledge_base/scripts/build_hybrid_vectors.py \
  --embedding-provider service \
  --embedding-service-url http://127.0.0.1:9100 \
  --embedding-batch-size 16
```

## kb-api 查询接入

当 `embedding_model.joblib` 中的 provider 是 `service` 时，`kb-api` 会读取：

```bash
KB_EMBEDDING_SERVICE_URL=http://embedding-service:9100
KB_EMBEDDING_SERVICE_TIMEOUT=30
```

如果 embedding 服务不可用，`kb-api` 会自动退回关键词检索，保证 AgentArts 接口不断。
