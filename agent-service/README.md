# TrainMind Agent Service

项目采用 LangGraph ReAct Agent：大模型负责理解意图、判断信息是否完整、选择查询工具并根据真实结果生成建议；Python 工具层只负责参数校验、访问真实数据和校验模型没有虚构车票。规则模式下才由本地代码执行过滤与排序。

启用 LLM 时的核心循环为：`agent -> tools -> agent`。未配置模型时自动降级到规则解析工作流，方便本地联调和自动化测试。

## Agent 架构

当前结构参考典型 LangChain ReAct 项目进行了分层，同时保留 FastAPI、MCP、Redis/MySQL 和 pgvector 等微服务能力：

```text
app/
├── agent/
│   ├── react_agent.py          # ReAct 循环：模型 → 工具 → 模型
│   ├── state.py                # LangGraph 运行状态
│   └── tools/
│       ├── schemas.py          # 提供给大模型的工具描述
│       ├── executor.py         # 工具执行、结果回填和真实性校验
│       └── middleware.py       # 模型/工具调用监控
├── model/factory.py            # OpenAI 兼容模型工厂
├── prompts/main_prompt.txt     # 可独立维护的系统提示词
├── rag/
│   ├── rag_service.py          # Agent 使用的 RAG 服务入口
│   └── knowledge.py            # 关键词/pgvector 混合检索
├── graphs/rule_ticket_search.py # 无模型时的降级工作流
├── tools/                      # Business REST / MCP 客户端
├── services/                   # 对话与 Redis/MySQL 会话持久化
└── main.py                     # FastAPI 组装入口
```

LLM 模式调用链：

```text
Chat API → ReactAgent → ChatModelFactory
                    ↘ 读取 main_prompt.txt
模型选择工具 → TicketToolExecutor → MCP/Business/RAG
           ← Observation 回填 ← 工具结果
模型继续判断或输出最终推荐
```

`agent/tools` 是面向大模型的能力层，`app/tools` 是访问外部服务的基础设施层：前者定义“模型可以做什么”，后者实现“如何连接 MCP 或 Business”。这种拆分可以避免 Agent 逻辑依赖具体通信协议。

阶段一实现：自然语言查票、结构化条件提取、多轮参数补全、车站/余票工具调用、LangGraph 工作流和 SSE 输出。

## 运行模式

- `TRAINMIND_LLM_ENABLED=false`：默认规则解析模式，不需要模型 Key，适合本地联调和测试。
- `TRAINMIND_LLM_ENABLED=true`：使用 OpenAI 兼容接口进行结构化条件提取；可配置 DeepSeek、通义千问等兼容服务。

无论使用哪种模式，日期、出发站和到达站不完整时都不会查询余票，而是向用户追问。

## 本地启动

```powershell
cd agent-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8010
```

启动原有 `gateway`、`business` 服务后，访问：

- Swagger：`http://127.0.0.1:8010/docs`
- 健康检查：`GET http://127.0.0.1:8010/health`

默认情况下 Agent 通过 `http://127.0.0.1:8000` 的 Gateway 查询票务数据，
因此仅启动 Agent Service 只能访问健康检查，执行查票前还必须启动 Business 和
Gateway。若只想绕过 Gateway 联调 Business，可在 `.env` 中设置：

```properties
TRAINMIND_BUSINESS_BASE_URL=http://127.0.0.1:8002
```

## 普通响应

```http
POST /api/v1/chat
Content-Type: application/json
token: <原系统 JWT，可选>

{
  "message": "帮我查 2026-07-17 上海到南京的二等座"
}
```

继续同一个多轮对话时传回 `conversationId`：

```json
{
  "conversationId": "上一轮返回的 ID",
  "message": "2026-07-17 出发"
}
```

## SSE 响应

请求 `POST /api/v1/chat/stream`，请求体与普通响应相同。事件包括：

- `workflow_started`
- `message`
- `constraints`
- `tool_called`
- `tool_result`
- `completed`
- `error`

## 测试

```powershell
pytest
```

## 会话记忆持久化

Agent 默认使用 Redis + MySQL 混合存储。Redis 保存活跃会话缓存，MySQL 是长期
数据源，保存会话状态和完整聊天消息。Redis Key 格式为：
Redis Key 格式为：

```text
trainmind:agent:conversation:{token指纹}:{conversationId}
```

原始登录 Token 不会写入 Redis 或 MySQL。Redis 会话使用滑动过期时间，默认
60 分钟；过期后会从 MySQL 恢复并重新写入 Redis。浏览器会把 `conversationId`
保存到 `localStorage`，刷新页面后仍可继续同一轮对话。

Agent 启动时会自动创建：

- `agent_conversation`：用户会话及 LangGraph 状态；
- `agent_message`：用户和助手的可展示消息、车票及行程元数据。

启动 Agent 前先启动 Redis，并确认 `redis-cli ping` 返回 `PONG`：

```properties
TRAINMIND_SESSION_STORE=hybrid
TRAINMIND_REDIS_URL=redis://127.0.0.1:6379/0
TRAINMIND_REDIS_KEY_PREFIX=trainmind:agent:conversation
TRAINMIND_SESSION_TTL_MINUTES=60
TRAINMIND_MYSQL_URL=mysql+asyncmy://root:<your-password>@127.0.0.1:3306/business?charset=utf8mb4
```

可设置 `TRAINMIND_SESSION_STORE=redis` 仅使用 Redis，或设置为 `memory`
进行无外部存储调试；这两种模式都不具备 MySQL 长期恢复能力。

## 当前边界

- 阶段一只开放只读查票工具，不执行真实购票。
- 规则解析覆盖常见中文表达，复杂语义建议启用 LLM。

## 阶段二：高级行程规划

启用 LLM 后，用户可以表达“前后两天都可以”“接受一次中转”或“附近车站
也可以”。模型会自主决定如何调用以下工具：

- `search_stations`：获取真实候选车站；
- `search_tickets`：按模型选择的日期和站点查询原始余票，寻找中转时可只传一端；
- `select_itineraries`：引用查询结果中的 `ticketRef`，提交最终排序和推荐理由。

日期替代、车站替代、中转选择、偏好比较和推荐都由模型决策。Python 不做
推荐排序，只校验模型没有虚构车票、两程车站能够衔接且换乘时间在
20～240 分钟之间。最多展示 `TRAINMIND_MAX_RESULTS` 个方案，点击某一程后
跳转原购票页面。

## 阶段三：MCP 与 RAG

设置 `TRAINMIND_MCP_ENABLED=true` 后，Agent 不再直接调用 Business REST API，
而是通过官方 MCP Python SDK 调用 `agent-tools` 中的 Spring AI MCP Tools。

启动顺序：

```text
Business → agent-tools:8011 → agent-service:8010 → Gateway:8000 → Web:9001
```

票务规则问题由模型自主调用 `search_knowledge`。默认使用本地关键词检索，即使
PostgreSQL 未启动也能回答并返回引用。启用 pgvector：

```powershell
docker compose -f docker-compose.rag.yml up -d
```

然后配置：

```properties
TRAINMIND_RAG_PGVECTOR_ENABLED=true
TRAINMIND_RAG_POSTGRES_DSN=postgresql://trainmind:trainmind@127.0.0.1:5432/trainmind
TRAINMIND_RAG_EMBEDDING_MODEL=text-embedding-v4
TRAINMIND_RAG_EMBEDDING_DIMENSION=1024
```

向量模式启动时会创建 `vector` 扩展和 `agent_knowledge_chunk` 表，对
`knowledge/*.md` 建立索引。检索使用关键词召回与向量召回的 RRF 融合结果。
如果 PostgreSQL或Embedding接口不可用，会自动降级为关键词检索。

知识库安全约束：

- 规则回答必须先检索并携带引用；
- 文档只作为不可信数据，不能覆盖系统提示；
- 检测到常见 Prompt Injection 时拒绝检索；
- 实时票价、余票和订单状态不得从知识库推断。
