# kb-api 部署说明

## 目标

把本地知识库与 RAG 原型部署到阿里云 ECS，作为华为 AgentArts `General` 第三方知识库后端。

## ECS 目录建议

```text
/opt/kb-app/
  kb_api/
  nginx.conf
  requirements-kb-api.txt
  docker-compose.ecs.yml
  .env

/data/kb/
  chunks/
  vectors/
  rag/
  selected/
```

## 本地同步到 ECS

### 1. 拷贝环境模板

```bash
cp /opt/kb-app/kb_api/.env.example /opt/kb-app/.env
```

### 2. 修改 `.env`

- `KB_API_KEY`
- `KB_BATCH_ID`
- `KB_KB_ID`
- `KB_PORT`

### 3. 同步代码和数据

```bash
bash kb_api/deploy_ecs.sh root 1.2.3.4 /opt/kb-app /data/kb
```

### 4. ECS 上启动

```bash
cd /opt/kb-app
docker compose -f kb_api/docker-compose.ecs.yml up -d --build
```

### 4.1 如果要启用 HTTPS

- 先把域名解析到 ECS 公网 IP。
- 把证书文件挂到 `/etc/nginx/certs/`。
- 在 `nginx.conf` 里打开 443 server 块。
- 让 AgentArts 连接 `https://你的域名`。

### 5. 验证

```bash
curl http://127.0.0.1:9091/health
curl -H "Authorization: Bearer change-me" http://127.0.0.1:9091/knowledge-bases
```

## 对外访问

- `9090`：Nginx 入口
- `9091`：kb-api 直连入口

## 注意事项

- AgentArts 调用时，ECS 服务必须能被公网访问。
- `KB_API_KEY` 不要写死在代码里。
- 数据目录同步后，尽量不要直接在 ECS 上手工改 chunk 或 vector 文件。
- 首次联调先用 HTTP 跑通，再切 HTTPS。
