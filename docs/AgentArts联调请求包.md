# AgentArts 联调请求包

本文档提供一套可直接复制的联调请求包，供 AgentArts `General` 知识库接入时快速验证。

## 1. 联调前准备

- 基础地址：`http://8.161.227.173:9090`
- 鉴权方式：`Authorization: Bearer <KB_API_KEY>`
- 当前测试密钥：`hbagent`
- 推荐优先联调的知识库：`ai_qna_standard_v1`

## 2. 快速连通性检查

### 2.1 健康检查

```bash
curl -sS http://8.161.227.173:9090/health \
  -H "Authorization: Bearer hbagent"
```

期望：

- `status` 为 `ok`
- `active_knowledge_base_id` 正确
- `embedding_model` 为当前线上模型

### 2.2 知识库列表

```bash
curl -sS http://8.161.227.173:9090/knowledge-bases \
  -H "Authorization: Bearer hbagent"
```

期望：

- 能返回至少一个知识库
- 当前激活库信息正常

## 3. 推荐检索请求

### 3.1 显式单库检索

这是 AgentArts 新接入时最推荐的方式。

```bash
curl -sS -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H "Authorization: Bearer hbagent" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "ai_qna_standard_v1",
    "query": "服务区危化品车辆现场处理流程是什么",
    "method": "doc",
    "offset": 0,
    "limit": 3,
    "top_k": 3,
    "search_threshold": 0.0,
    "extra_params": []
  }'
```

期望：

- `total > 0`
- `search_result_list` 有内容
- 结果包含 `source_file`、`section_path`、`knowledge_base_id`

### 3.2 兼容旧字段检索

如果现有 Agent 还没改造完，可以先用旧字段兼容。

```bash
curl -sS -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H "Authorization: Bearer hbagent" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_ids": ["ai_qna_standard_v1"],
    "query": "服务区危化品车辆现场处理流程是什么",
    "method": "doc",
    "offset": 0,
    "limit": 3,
    "top_k": 3,
    "search_threshold": 0.0,
    "extra_params": []
  }'
```

期望：

- 与显式单库检索结果一致或接近
- 能证明旧调用方式仍然兼容

### 3.3 冲突请求验证

这个请求用于验证路由冲突保护是否生效。

```bash
curl -sS -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H "Authorization: Bearer hbagent" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "ai_qna_standard_v1",
    "knowledge_base_ids": ["ai_qna_standard_v2"],
    "query": "服务区危化品车辆现场处理流程是什么"
  }'
```

期望：

- 返回 `400`
- 提示 `knowledge_base_id` 必须包含在 `knowledge_base_ids` 中

## 4. AgentArts 对接建议

### 4.1 推荐输入

AgentArts 调用知识平台时，建议固定传入：

- `knowledge_base_id`
- `query`
- `top_k`
- `limit`

### 4.2 推荐输出消费方式

AgentArts 侧建议优先消费这些字段：

- `content`
- `title`
- `source_file`
- `section_path`
- `knowledge_base_id`
- `retrieval_mode`

### 4.3 推荐使用顺序

1. 先做 `health` 和 `knowledge-bases` 连通性验证
2. 再做显式单库检索
3. 再做旧字段兼容检索
4. 最后接真实业务问题

## 5. 典型业务问题

可优先验证以下问题：

- 危化品车辆现场实际的处理流程是什么
- 拥堵判断条件有哪些
- 违规收银的处理规范是什么
- 设备巡检发现异常后怎么闭环

## 6. 成功判定

满足以下条件即可认为基础联调通过：

- 接口可达
- 显式单库检索可用
- 旧字段兼容可用
- 返回证据可追溯
- 真实业务问题可命中资料

