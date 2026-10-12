# TrainMind：基于多智能体协作的智能铁路票务平台技术方案

## 1. 文档概述

### 1.1 项目背景

现有 Train 项目是一个基于 Spring Boot、Spring Cloud 和 Vue 3 的前后端分离火车票务系统，已经具备会员管理、乘车人管理、车次管理、余票查询、购票排队、异步出票和定时任务等能力。

本方案在不破坏原有高并发购票链路的前提下，引入大语言模型、Agent 工作流、RAG、MCP 和 Human-in-the-loop，将系统升级为能够通过自然语言完成行程规划、票务查询、辅助购票和运营分析的智能铁路票务平台。

### 1.2 项目名称

**TrainMind——基于多智能体协作的智能铁路票务平台**

### 1.3 建设目标

- 支持用户通过自然语言查询车次、余票和票价。
- 自动提取日期、车站、时间、座席和价格等约束条件。
- 支持多轮对话补全缺失参数，并给出可解释的车次推荐。
- 在用户明确确认后，调用原有购票服务创建订单并跟踪出票状态。
- 使用 RAG 回答退改签、乘车须知等票务规则问题，并提供知识来源。
- 为管理端提供票务数据分析、异常发现和运营建议。
- 建立 Agent 调用审计、链路追踪、安全控制和离线评测体系。

### 1.4 非建设目标

- Agent 不直接读写业务数据库。
- Agent 不绕过现有 Redis 令牌、RocketMQ 排队和 Seata 事务链路。
- Agent 不在未经用户确认的情况下执行购票、取消订单等写操作。
- 第一阶段不允许 Agent 自动修改车次、座位、库存等运营数据。

---

## 2. 业务场景

### 2.1 智能行程规划

用户输入：

> 帮我查周五晚上从上海去南京的车，优先二等座，最晚 22 点到，价格不要超过 200 元。

系统处理过程：

1. 识别用户意图为车票查询或辅助购票。
2. 将“周五”转换成具体日期。
3. 提取出发站、到达站、时间、座席和价格约束。
4. 查询符合条件的车次和实时余票。
5. 根据到达时间、耗时、票价和余票生成推荐排序。
6. 返回结构化结果及推荐理由。

### 2.2 多轮参数补全

当用户输入“帮我买一张去南京的票”时，Agent 需要逐步补充：

- 出发城市或车站；
- 出发日期；
- 期望时间范围；
- 座席类型；
- 乘车人。

Agent 不能在关键参数不完整时猜测并直接下单。

### 2.3 辅助购票

1. Agent 根据用户需求推荐车次。
2. 用户选择车次和乘车人。
3. Agent 创建购票草稿。
4. 系统展示车次、日期、区间、座席、乘车人和预估价格。
5. 工作流暂停，等待用户确认。
6. 用户确认后，系统获得一次性审批令牌。
7. Agent 调用现有购票接口提交订单。
8. Agent 查询排队位置并向用户持续反馈最终结果。

### 2.4 票务知识问答

Agent 通过 RAG 回答：

- 退票和改签规则；
- 儿童票、学生票规则；
- 行李携带要求；
- 乘车和检票须知；
- 平台购票、支付和排队说明。

回答需要携带引用文档、章节和版本信息，降低模型幻觉。

### 2.5 运营分析

管理端可以通过自然语言查询：

- 热门线路和热门车次；
- 订单成功率、失败率和无票率；
- 平均排队时间和出票耗时；
- 不同座席的售罄速度；
- 余票数据异常和积压订单；
- 每日运营摘要和调整建议。

运营 Agent 第一阶段只提供查询与建议，不直接执行数据变更。

---

## 3. 总体架构

```text
┌────────────────────────────────────────────────────────────┐
│                 Vue 用户端 / Vue 管理端                    │
│          对话界面、推荐卡片、审批卡片、执行轨迹             │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTP / SSE
                           ▼
┌────────────────────────────────────────────────────────────┐
│                    Spring Cloud Gateway                    │
│           JWT 校验、统一路由、限流、Trace ID 透传           │
└───────────┬──────────────────────────────┬─────────────────┘
            │                              │
            ▼                              ▼
┌──────────────────────────┐   ┌─────────────────────────────┐
│ agent-service            │   │ 原有 Java 微服务            │
│ FastAPI + LangGraph      │   │ member / business / batch   │
│                          │   │                             │
│ - Supervisor Agent       │   │ MySQL / Redis / RocketMQ    │
│ - Travel Planner Agent   │   │ Sentinel / Seata / Quartz   │
│ - Booking Agent          │   └──────────────▲──────────────┘
│ - Knowledge Agent        │                  │
│ - Agent State & Memory   │                  │ REST / Feign
└────────────┬─────────────┘                  │
             │ MCP / Tool Calling             │
             ▼                                │
┌─────────────────────────────────────────────┴──────────────┐
│ agent-tools：Spring AI MCP Server                          │
│ 工具定义、参数校验、身份透传、幂等控制、权限控制、审计日志 │
└────────────────────────────────────────────────────────────┘
             │
             ├── PostgreSQL + pgvector：知识库、Checkpoint
             ├── Redis：会话缓存、审批令牌、幂等键
             └── LLM：DeepSeek / 通义千问 / OpenAI 兼容模型
```

### 3.1 架构原则

- **确定性流程优先**：LLM 负责语义理解和候选决策，状态图负责流程控制。
- **业务服务是事实源**：余票、价格、乘车人和订单状态必须来自现有服务。
- **读写工具分离**：查询工具可以自动调用，写工具必须经过审批。
- **最小权限**：只向 Agent 暴露完成当前任务所需的工具。
- **可恢复执行**：长流程保存 Checkpoint，服务重启后可以继续。
- **全链路可观测**：每次模型调用、工具调用和工作流状态变化均可追踪。

---

## 4. 技术选型

| 层次 | 技术 | 用途 |
| --- | --- | --- |
| Agent 服务 | Python 3.12、FastAPI | Agent API、SSE 流式响应 |
| Agent 编排 | LangGraph | 状态图、多 Agent、Checkpoint、人工审批 |
| 模型接入 | LangChain Model API | 屏蔽不同模型供应商差异 |
| 数据校验 | Pydantic | 结构化输出、状态和工具参数校验 |
| Java AI 集成 | Spring AI | Tool Calling、MCP Server、模型能力扩展 |
| 工具协议 | MCP | 标准化暴露 Tools、Resources 和 Prompts |
| RAG | PostgreSQL、pgvector | 文档存储、向量检索和混合检索 |
| 会话缓存 | Redis | 短期记忆、幂等键、审批令牌 |
| 业务服务 | Spring Boot、Spring Cloud | 复用原有票务能力 |
| 消息队列 | RocketMQ | 异步排队购票 |
| 分布式事务 | Seata | 跨 business、member 服务事务一致性 |
| 可观测性 | OpenTelemetry、Prometheus、Grafana | Trace、指标和告警 |
| Agent 观测 | Langfuse 或兼容平台 | Prompt、Token、工具调用和评测记录 |
| 部署 | Docker Compose | 本地一键启动与演示 |

### 4.1 为什么 Agent 服务独立部署

现有项目使用 Spring Boot 3.0.0 和较早版本的 Spring Cloud 依赖。将最新 Agent 框架直接加入原有业务模块可能引入依赖冲突，也会让模型调用占用业务服务线程。

因此采用独立 `agent-service`：

- Agent 框架可以独立升级；
- Java 业务服务保持稳定；
- Agent 服务可以单独扩容和限流；
- Python 生态便于使用 LangGraph 及配套评测工具；
- 通过 MCP 和受控 REST API 与 Java 服务解耦。

---

## 5. 多 Agent 设计

### 5.1 Supervisor Agent

职责：

- 识别 `TICKET_SEARCH`、`BOOK_TICKET`、`KNOWLEDGE_QA` 和 `OPERATION_ANALYSIS` 等意图；
- 根据意图选择后续 Agent；
- 识别任务是否完成；
- 控制最大执行步数，防止循环调用。

Supervisor 不直接调用购票写工具。

### 5.2 Travel Planner Agent

职责：

- 提取并校验出发站、到达站、日期、时间范围、座席和价格；
- 对缺失信息发起追问；
- 查询车站、车次和余票；
- 计算候选车次排序；
- 生成带事实依据的推荐理由；
- 在无直达车时规划一次换乘方案。

### 5.3 Booking Agent

职责：

- 获取当前会员的乘车人列表；
- 接收用户选定的车次和乘车人；
- 创建购票草稿；
- 发起 Human-in-the-loop 审批；
- 审批通过后提交订单；
- 跟踪排队位置和出票结果；
- 处理无票、限流、超时和服务异常。

### 5.4 Knowledge Agent

职责：

- 对问题进行查询改写；
- 从知识库检索候选片段；
- 对候选片段进行重排；
- 基于检索证据生成答案；
- 返回文档名称、章节、版本和引用片段。

### 5.5 Operation Agent

职责：

- 将自然语言分析需求转换为预定义指标查询；
- 汇总订单、车次和排队指标；
- 识别异常趋势；
- 生成日报和运营建议。

禁止模型自由生成并执行 SQL。复杂查询需要通过受控指标 API 或只读查询模板实现。

---

## 6. Agent 状态图

```text
START
  │
  ▼
识别意图
  ├── KNOWLEDGE_QA ──> RAG 检索 ──> 生成带引用回答 ──> END
  │
  ├── OPERATION_ANALYSIS ──> 指标查询 ──> 分析报告 ──> END
  │
  └── TICKET_SEARCH / BOOK_TICKET
          │
          ▼
      提取结构化条件
          │
          ▼
      参数是否完整？
       ├── 否 ──> 询问用户 ──> 保存状态 ──> 等待回复
       └── 是
            │
            ▼
        查询并推荐车次
            │
            ▼
        用户是否要求购买？
         ├── 否 ──> END
         └── 是
              │
              ▼
          选择乘车人
              │
              ▼
          创建购票草稿
              │
              ▼
          人工确认中断
          ├── 拒绝 ──> 取消草稿 ──> END
          └── 同意
                │
                ▼
            提交购票订单
                │
                ▼
            查询排队状态
                │
                ▼
      SUCCESS / EMPTY / FAILURE / TIMEOUT
```

### 6.1 工作流状态模型

```json
{
  "conversationId": "01J...",
  "memberId": 10001,
  "intent": "BOOK_TICKET",
  "constraints": {
    "date": "2026-07-17",
    "start": "上海",
    "end": "南京",
    "departAfter": "18:00",
    "arrivalBefore": "22:00",
    "seatTypes": ["EDZ"],
    "maxPrice": 200
  },
  "candidateTrains": [],
  "selectedTrain": null,
  "passengerIds": [],
  "draftId": null,
  "approvalStatus": "WAITING",
  "orderId": null,
  "toolCallCount": 0,
  "lastError": null
}
```

---

## 7. MCP 工具设计

### 7.1 只读工具

| 工具 | 说明 | 后端能力 |
| --- | --- | --- |
| `search_stations` | 根据城市或关键词搜索车站 | business station |
| `search_tickets` | 根据日期和区间查询车次及余票 | daily-train-ticket |
| `get_train_detail` | 查询车次、经停站和时刻信息 | train、train-station |
| `get_remaining_tickets` | 查询指定区间和席位余票 | daily-train-ticket |
| `list_passengers` | 查询当前用户乘车人 | member passenger |
| `get_order_status` | 查询确认订单状态 | confirm-order |
| `get_queue_position` | 查询当前排队位置 | query-line-count |
| `query_operation_metrics` | 查询预定义运营指标 | admin aggregate API |

### 7.2 写操作工具

| 工具 | 说明 | 安全要求 |
| --- | --- | --- |
| `create_booking_draft` | 创建购票草稿，不执行真实下单 | 登录校验、参数校验 |
| `confirm_booking` | 根据草稿执行真实下单 | 审批令牌、幂等键、资源归属校验 |
| `cancel_booking` | 取消允许取消的订单 | 二次确认、订单归属校验 |

### 7.3 工具调用约束

- Agent 不接收或传递数据库连接信息。
- `memberId` 从 JWT 或服务上下文读取，不能完全信任模型参数。
- 乘车人必须属于当前登录用户。
- 写操作必须携带 `approvalToken` 和 `idempotencyKey`。
- 审批令牌只允许使用一次，并设置较短有效期。
- 每个会话限制模型轮数和工具调用次数。
- 工具参数使用 JSON Schema 和服务端 Bean Validation 双重校验。
- 工具响应只返回 Agent 完成任务所需字段，避免敏感信息泄露。
- 所有工具调用记录调用人、会话、参数摘要、结果和耗时。

### 7.4 工具返回协议

```json
{
  "success": true,
  "code": "SUCCESS",
  "message": "ok",
  "traceId": "trace-xxx",
  "data": {},
  "retryable": false
}
```

Agent 依据稳定错误码处理异常，不能依赖自然语言错误消息进行流程判断。

---

## 8. Human-in-the-loop 设计

### 8.1 必须审批的操作

- 提交购票订单；
- 取消订单；
- 修改乘车人资料；
- 任何运营数据写操作。

### 8.2 购票审批卡片

审批页面展示：

- 出发站和到达站；
- 日期、车次、出发和到达时间；
- 乘车人；
- 座席类型；
- 票价和订单数量；
- 余票快照时间；
- Agent 推荐理由；
- “确认购票”和“取消”按钮。

### 8.3 审批流程

1. Agent 创建不可执行的购票草稿。
2. LangGraph 保存 Checkpoint 并中断工作流。
3. 前端展示审批卡片。
4. 用户确认后，后端生成一次性 `approvalToken`。
5. 恢复工作流并调用 `confirm_booking`。
6. 工具服务再次核对草稿内容、用户身份和令牌。
7. 调用原有购票接口并废弃审批令牌。

用户在审批后修改车次、乘车人或席位时，原审批令牌立即失效，需要重新确认。

---

## 9. RAG 知识库设计

### 9.1 文档目录

```text
knowledge/
├── ticket-refund.md
├── ticket-change.md
├── passenger-rules.md
├── student-and-child-ticket.md
├── baggage-rules.md
├── boarding-guide.md
└── platform-operation-manual.md
```

### 9.2 文档元数据

```json
{
  "documentId": "ticket-refund",
  "title": "退票规则",
  "section": "开车前退票",
  "version": "2026-01",
  "effectiveFrom": "2026-01-01",
  "effectiveTo": null,
  "source": "内部票务规则",
  "visibility": "PUBLIC"
}
```

### 9.3 检索流程

```text
用户问题
   ↓
查询改写与关键词提取
   ↓
向量检索 + 关键词检索
   ↓
按有效期和权限过滤
   ↓
Reranker 重排
   ↓
基于证据生成答案
   ↓
返回引用和置信度
```

### 9.4 防幻觉规则

- 没有足够证据时明确说明无法确定。
- 票价、余票和订单状态只能通过实时工具查询。
- 知识回答必须携带来源。
- 过期文档不得用于生成当前规则答案。
- 检索到相互冲突的规则时提示人工确认。

---

## 10. 接口设计

### 10.1 创建或继续对话

```http
POST /agent/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "conversationId": "可选",
  "message": "帮我查周五晚上上海到南京的二等座"
}
```

响应通过 SSE 返回：

```text
event: node_started
data: {"node":"extract_constraints"}

event: tool_called
data: {"tool":"search_tickets","status":"RUNNING"}

event: message
data: {"content":"找到 3 个符合条件的车次"}

event: approval_required
data: {"draftId":"D10001"}

event: completed
data: {"conversationId":"C10001"}
```

### 10.2 审批购票

```http
POST /agent/approvals/{draftId}/approve
Authorization: Bearer <token>
Idempotency-Key: <uuid>
```

### 10.3 拒绝购票

```http
POST /agent/approvals/{draftId}/reject
Authorization: Bearer <token>
```

### 10.4 查询会话状态

```http
GET /agent/conversations/{conversationId}
Authorization: Bearer <token>
```

---

## 11. 数据存储设计

### 11.1 Agent 会话表

```text
agent_conversation
├── id
├── member_id
├── title
├── status
├── current_node
├── model_name
├── created_at
└── updated_at
```

### 11.2 消息表

```text
agent_message
├── id
├── conversation_id
├── role
├── content
├── token_count
├── trace_id
└── created_at
```

### 11.3 工具调用表

```text
agent_tool_call
├── id
├── conversation_id
├── tool_name
├── arguments_digest
├── result_code
├── duration_ms
├── approved_by_user
├── trace_id
└── created_at
```

### 11.4 购票草稿表

```text
booking_draft
├── id
├── member_id
├── train_date
├── train_code
├── start_station
├── end_station
├── seat_type
├── passenger_snapshot
├── price_snapshot
├── status
├── expires_at
└── created_at
```

敏感参数不以明文写入 Agent 观测平台，日志中只保存脱敏值或摘要。

---

## 12. 安全设计

### 12.1 身份与权限

- Gateway 统一校验 JWT。
- Agent 服务只信任 Gateway 签发或内部验证通过的身份上下文。
- MCP 工具服务再次校验用户身份和资源归属。
- 管理端工具与用户端工具使用不同权限域。

### 12.2 Prompt Injection 防护

- 系统提示、用户输入、RAG 文档和工具结果分别标记信任级别。
- RAG 文档内容只作为数据，不作为系统指令执行。
- 工具权限由服务端策略决定，模型无法通过提示扩大权限。
- 检测“忽略之前指令”“泄露系统提示”“调用管理工具”等高风险内容。
- 写操作始终需要用户审批，不能仅凭模型判断执行。

### 12.3 业务安全

- 下单接口支持幂等键。
- 草稿、审批令牌和订单必须属于同一用户。
- 价格和余票在最终下单前重新校验。
- 写工具设置调用频率和金额上限。
- Agent 不缓存完整身份证号、手机号等敏感信息。

### 12.4 Agent 运行限制

- 单轮最大模型调用次数；
- 单任务最大工具调用次数；
- 单工具超时时间；
- 单会话 Token 预算；
- 可重试错误白名单；
- 连续失败熔断；
- 循环状态检测。

---

## 13. 可观测性设计

### 13.1 Trace 链路

```text
Vue → Gateway → agent-service → MCP Tool
    → business → RocketMQ → member
```

使用同一个 `traceId` 贯穿 Agent 节点、模型调用、工具调用、HTTP 调用和 MQ 消息。

### 13.2 核心指标

#### Agent 指标

- 意图识别准确率；
- 参数提取准确率；
- 任务完成率；
- 平均对话轮数；
- 平均工具调用次数；
- 无效工具调用率；
- 人工审批通过率；
- 单任务 Token 消耗和模型成本。

#### 系统指标

- Agent API P50、P95、P99 延迟；
- MCP 工具成功率和超时率；
- RocketMQ 消息积压；
- 平均排队和出票时间；
- Redis 命中率；
- 订单成功率和无票率。

### 13.3 日志要求

- 记录模型名称、Prompt 版本和工作流版本；
- 记录工具名称、参数摘要、返回码和耗时；
- 不记录 API Key、JWT、完整证件号和手机号；
- 写操作保留不可抵赖的审批审计记录。

---

## 14. Agent 评测方案

### 14.1 离线评测集

```json
{
  "caseId": "booking-001",
  "question": "帮我买周五上海去南京最晚十点到的二等座",
  "expectedIntent": "BOOK_TICKET",
  "requiredSlots": [
    "date",
    "start",
    "end",
    "arrivalBefore",
    "seatType"
  ],
  "expectedTools": ["search_tickets"],
  "forbiddenTools": ["confirm_booking"],
  "requiresApproval": true
}
```

### 14.2 评测维度

- 意图路由是否正确；
- 日期和实体解析是否正确；
- 缺少参数时是否追问；
- 工具选择和参数是否正确；
- 未审批时是否禁止下单；
- 余票不足时是否停止流程；
- RAG 回答是否忠于检索证据；
- 工具超时后是否正确重试或降级；
- Prompt Injection 是否被拒绝；
- 对相同输入是否保持关键行为一致。

### 14.3 测试类型

- Agent 节点单元测试；
- 工具 Schema 和参数校验测试；
- MCP 契约测试；
- 使用 Mock LLM 的确定性流程测试；
- 使用真实模型的离线回归测试；
- 业务服务集成测试；
- JMeter 并发和稳定性测试；
- 故障注入测试，包括 Redis、MQ、模型和工具服务超时。

---

## 15. 项目目录规划

```text
train/
├── common/
├── gateway/
├── member/
├── business/
├── batch/
├── generator/
├── web/
├── admin/
├── agent-service/                 # 新增：Python Agent 编排服务
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── graphs/
│   │   ├── models/
│   │   ├── tools/
│   │   ├── rag/
│   │   ├── memory/
│   │   ├── security/
│   │   └── observability/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── agent-tools/                   # 新增：Spring AI MCP Server
│   ├── pom.xml
│   └── src/main/
├── knowledge/                     # 新增：RAG 文档
├── evaluation/                    # 新增：评测集和评测脚本
├── deploy/                        # 新增：容器和监控配置
├── docker-compose.yml
└── TRAINMIND_TECHNICAL_DESIGN.md
```

---

## 16. 现有模块改造点

### 16.1 gateway

- 增加 `/agent/**` 路由；
- 透传 JWT、Trace ID 和语言信息；
- 对 Agent 接口单独配置限流；
- SSE 接口关闭不合适的响应缓存和短超时。

### 16.2 business

- 增加面向 Agent 的车次聚合查询接口；
- 统一车次、余票和票价返回模型；
- 增加购票草稿校验接口；
- 下单接口增加幂等键；
- 订单状态查询返回稳定错误码。

### 16.3 member

- 增加当前用户乘车人简要信息接口；
- Feign 接口增加用户身份和 Trace ID 透传；
- 强化乘车人资源归属校验。

### 16.4 web

- 新增聊天侧边栏或独立智能助手页面；
- 支持 Markdown、车次推荐卡片和引用展示；
- 支持 SSE 流式消息；
- 新增购票审批卡片和执行进度时间线。

### 16.5 admin

- Agent 会话检索；
- 模型和 Prompt 版本管理；
- 工具调用审计；
- Token 成本和响应延迟面板；
- Agent 评测结果页面；
- 运营分析报告页面。

---

## 17. 异常与降级策略

| 异常 | 处理策略 |
| --- | --- |
| LLM 超时 | 有限次数重试，随后提示用户稍后重试 |
| LLM 不可用 | 降级到传统表单查询入口 |
| MCP 工具超时 | 根据工具幂等性决定是否重试 |
| Redis 不可用 | 禁止写操作，查询操作按业务能力降级 |
| RocketMQ 发送失败 | 保持订单可恢复状态并返回明确错误 |
| 排队状态长时间未更新 | 停止高频轮询，转为后台通知 |
| RAG 无有效证据 | 明确说明知识库中没有可靠答案 |
| 结构化输出校验失败 | 自动修复一次，仍失败则重新询问 |
| Agent 陷入循环 | 达到步数限制后中止并记录告警 |

---

## 18. 实施计划

### 阶段一：自然语言查票 MVP

目标：完成可演示的自然语言票务查询闭环。

- 创建 `agent-service`；
- 接入一个支持 Tool Calling 的模型；
- 实现意图识别和约束提取；
- 封装车站、车次和余票查询工具；
- 实现多轮参数补全；
- 增加 Web 对话界面和 SSE；
- 编写基础单元测试和演示数据。

### 阶段二：高级行程规划

目标：由大模型自主调用数据工具，生成可解释的组合行程方案。

- Python 只提供车站查询、宽条件余票查询和方案提交工具；
- LLM 自主决定查询哪些日期、车站以及是否寻找一次中转；
- LLM 自主比较时间、余票、席别、价格并生成排序和推荐理由；
- 最终方案只允许通过 `ticketRef` 引用工具返回的真实车票；
- Python 仅校验票号真实性、两程站点衔接和 20～240 分钟换乘窗口；
- 前端展示模型选出的总耗时、总价、换乘时间和分段车次；
- 每一程可跳转原购票页面，Agent 不进入高并发交易链路。

### 阶段三：MCP 与 RAG

目标：增强标准化扩展能力和知识问答能力。

- 新增 Spring AI MCP Server；
- 将票务能力迁移为标准 MCP Tools；
- 建设票务知识文档；
- 使用 pgvector 构建向量库；
- 实现混合检索、重排和引用；
- 增加 Prompt Injection 防护。

### 阶段四：工程化与运营 Agent

目标：达到简历项目和技术答辩要求。

- 增加 OpenTelemetry 全链路追踪；
- 接入 Prometheus 和 Grafana；
- 建立 Agent 离线评测集；
- 增加工具调用、Token 和成本面板；
- 实现只读运营分析 Agent；
- 补充 Docker Compose 和部署文档；
- 完成并发压测和评测报告。

---

## 19. 验收标准

### 19.1 功能验收

- 能从自然语言中正确提取票务约束；
- 缺少关键参数时能够准确追问；
- 能查询并解释推荐至少三个候选车次；
- 推荐车次能够携带查询参数跳转原购票页面；
- Agent 无法直接调用真实下单、库存扣减和订单状态工具；
- 知识问答能够返回有效引用；
- Agent 服务重启后可以恢复未完成工作流。

### 19.2 安全验收

- 无法通过提示词调用未授权工具；
- 无法为其他用户的乘车人下单；
- 重复请求不会创建重复订单；
- 日志不包含 Token、API Key 和完整敏感身份信息；
- 所有写操作均有审批与审计记录。

### 19.3 性能验收建议

- 非模型工具接口 P95 小于 500 ms；
- 首个 SSE 内容在模型正常时尽量控制在 2 秒内；
- Agent 工具调用成功率不低于 99%；
- 工作流恢复成功率不低于 99%；
- Agent 服务异常不影响传统购票入口。

实际指标应根据本地机器、模型供应商和部署环境调整，并在压测报告中说明测试条件。

---

## 20. 风险与应对

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 模型幻觉 | 返回错误车次或规则 | 实时数据只走工具，知识回答必须引用 |
| 模型输出不稳定 | 工作流无法继续 | Pydantic 校验、有限重试、确定性状态图 |
| 未授权工具调用 | 产生业务和安全风险 | 服务端鉴权、工具白名单、人工审批 |
| Agent 调用成本过高 | 项目运行成本增加 | 模型路由、缓存、Token 预算、摘要记忆 |
| 框架版本变化 | 升级维护成本 | Agent 独立部署，通过 MCP 解耦 |
| 依赖服务较多 | 本地运行困难 | Docker Compose、Mock 模式、最小演示环境 |
| 旧项目缺少测试 | 改造回归风险 | 先补核心购票链路集成测试和契约测试 |

---

## 21. 简历描述参考

### TrainMind——基于多智能体协作的高并发铁路票务平台

- 基于 Spring Cloud、LangGraph 和大语言模型，将传统火车票微服务升级为支持自然语言查票、行程规划及辅助购票的智能体系统。
- 采用 Supervisor、Travel Planner、Booking 和 Knowledge Agent 协作架构，通过状态图编排复杂任务，实现多轮参数补全、工具调用、执行中断与失败恢复。
- 基于 MCP 将车次、余票、乘车人和订单能力封装为标准化工具，通过 JWT 透传、幂等控制、工具白名单和审计日志保证 Agent 调用安全。
- 设计 Human-in-the-loop 购票流程，在执行有副作用的下单操作前持久化任务状态并等待用户确认，避免模型误操作。
- 基于 pgvector 构建票务规则 RAG 知识库，结合混合检索、重排和来源引用降低模型幻觉。
- 串联 Redis 购票令牌、Sentinel 限流、RocketMQ 异步排队及 Seata 分布式事务，保障高并发购票场景下的库存一致性。
- 建立 Agent 离线评测集和全链路可观测体系，统计意图识别准确率、任务成功率、工具调用成功率、响应延迟与 Token 成本。

---

## 22. 面试讲解主线

建议按照以下顺序介绍项目：

1. 原系统已经解决高并发购票和分布式事务问题。
2. TrainMind 解决传统票务系统交互复杂、规则查询分散的问题。
3. LLM 不直接操作数据库，而是通过 MCP 调用受控业务工具。
4. LLM 负责语义理解，LangGraph 负责确定性流程和恢复。
5. 写操作使用 Human-in-the-loop、幂等键和一次性审批令牌。
6. 实时数据来自业务工具，规则知识来自带引用的 RAG。
7. 使用评测集和 Trace 证明 Agent 不只是“看起来能用”，而是可以测试、观测和治理。

该主线可以同时体现 Java 微服务能力、分布式系统能力和 Agent 工程化能力。
