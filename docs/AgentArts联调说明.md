# AgentArts 联调说明

## 1. 目标

本说明用于指导 AgentArts `General` 第三方知识库与本知识平台进行联调。

联调目标有三个：

- 验证平台接口可达
- 验证检索请求可正常返回证据
- 验证知识库路由、引用和空库兜底行为正确

## 2. 联调前提

联调前需要确认：

- ECS 入口可访问
- `kb-api` 服务已启动
- `KB_API_KEY` 已配置
- 当前正式知识库已完成预处理、chunk 和 embedding
- `knowledge_bases.json` 中已存在可用知识库

## 3. 推荐联调顺序

### 3.1 第一阶段：连通性验证

先确认以下接口可访问：

- `GET /health`
- `GET /knowledge-bases`
- `GET /knowledge-base-registry`

### 3.2 第二阶段：检索验证

使用 `POST /knowledge-bases/retrieve` 进行问答检索验证。

建议先用显式 `knowledge_base_id`，再验证旧版 `knowledge_base_ids` 兼容写法。

### 3.3 第三阶段：业务验证

选择真实业务问题进行验证，例如：

- 危化品车辆现场处理流程
- 拥堵处理规则
- 违规收银规则
- 设备巡检要求

验证时重点看：

- 是否能返回真实证据
- 是否能追溯到来源文件和章节
- 是否命中业务规则
- 是否返回 `hybrid` 检索模式

## 4. 推荐测试项

更完整的复制粘贴请求包见：[AgentArts联调请求包.md](/Users/chenzhuo/hb/knowledge_base/docs/AgentArts联调请求包.md)。

### 4.1 健康检查

```bash
curl -H "Authorization: Bearer <KB_API_KEY>" http://8.161.227.173:9090/health
```

期望：

- `status = ok`
- `active_knowledge_base_id` 正确
- `embedding_model = bge-small-zh-v1.5`

### 4.2 知识库列表

```bash
curl -H "Authorization: Bearer <KB_API_KEY>" http://8.161.227.173:9090/knowledge-bases
```

期望：

- 至少返回一个知识库
- 当前激活库文档数和 chunk 数正常

### 4.3 显式单库检索

```bash
curl -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H "Authorization: Bearer <KB_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "ai_qna_standard_v1",
    "query": "服务区危化品车辆现场处理流程是什么",
    "top_k": 3,
    "limit": 3,
    "search_threshold": 0.0
  }'
```

期望：

- `total > 0`
- `search_result_list` 可返回内容
- 至少一条结果带有来源信息

### 4.4 兼容旧字段检索

```bash
curl -X POST http://8.161.227.173:9090/knowledge-bases/retrieve \
  -H "Authorization: Bearer <KB_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_ids": ["ai_qna_standard_v1"],
    "query": "服务区危化品车辆现场处理流程是什么",
    "top_k": 3,
    "limit": 3,
    "search_threshold": 0.0
  }'
```

期望：

- 与单库检索结果一致或近似一致
- 路由兼容稳定

## 5. 联调关注点

### 5.1 返回字段

AgentArts 侧需要关注以下字段：

- `content`
- `title`
- `source_file`
- `section_path`
- `knowledge_base_id`
- `retrieval_mode`

### 5.2 引用能力

回答结果中应尽量带上：

- 来源文件
- 章节路径
- 版本信息

### 5.3 路由能力

联调时尽量显式传 `knowledge_base_id`，这样不同业务线或不同 Agent 不会串库。

### 5.4 兜底能力

如果知识库暂时为空或未建索引，接口应返回空结果，不应直接报错。

## 6. 联调判定标准

满足以下条件时，可认为联调基础通过：

- 健康检查正常
- 显式单库检索正常
- 旧字段兼容检索正常
- 返回结果可追溯
- 业务问题能命中正确资料

## 7. 推荐对接方式

AgentArts 建议作为第一个外部消费者，先接入统一检索接口。

后续如果还要接其他平台，可以保持同一套检索协议，只替换 adapter 层。
