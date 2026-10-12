# TrainMind Agent 2.0 技术设计

> 定位：面向高并发票务系统的智能行程规划平台。Agent 负责查询、规划、解释和推荐，不直接执行抢票、扣库存或支付。

## 1. 技术选型结论

TrainMind Agent 2.0 采用以下组合：

- **总体架构：Hierarchical Multi-Agent（分层多 Agent）**
- **主 Agent：Plan-and-Execute + Dynamic Replanning**
- **专业 Agent：ReAct（Reasoning + Acting）**
- **质量控制：Evaluator-Optimizer + Reflexion**
- **Agent 通信：A2A 1.0**
- **工具接入：Function Calling + MCP**
- **流程能力复用：Agent Skills（`SKILL.md`）**
- **工作流框架：LangGraph StateGraph**
- **服务框架：FastAPI + Pydantic + SSE**
- **短期记忆：LangGraph Checkpointer + Redis**
- **长期记忆：MySQL 结构化存储 + Qdrant 语义记忆**
- **RAG：BGE-M3 + Qdrant Dense/Sparse Hybrid Search + RRF + BGE Reranker**
- **评估与追踪：RAGAS + LangSmith + 业务自定义指标**

这套方案没有让所有 Agent 都访问全部工具。每个专业 Agent 只拥有完成自身任务所需的上下文和权限，从架构上限制误调用和高风险操作。

## 2. 总体架构

```text
Web / App
    │  HTTP + SSE
    ▼
┌──────────────────────────────────────────────────────┐
│ Orchestrator Agent                                   │
│ Plan → Dispatch → Observe → Replan → Synthesize      │
│ LangGraph State + Redis Checkpoint + Memory Retriever│
└───────────────┬───────────────────┬──────────────────┘
                │ A2A               │ A2A
        ┌───────▼────────┐  ┌───────▼─────────┐
        │ Ticket Agent   │  │ Policy RAG Agent│
        │ ReAct Worker   │  │ Corrective RAG  │
        └───────┬────────┘  └───────┬─────────┘
                │ MCP               │ Qdrant
        ┌───────▼────────┐  ┌───────▼─────────┐
        │ Spring AI MCP  │  │ Dense + Sparse  │
        │ Read-only Tools│  │ RRF + Reranker  │
        └───────┬────────┘  └─────────────────┘
                │ REST / OpenFeign
        ┌───────▼─────────────────────────────┐
        │ Java Ticket Microservices           │
        │ Station / Ticket / Order / Inventory│
        └─────────────────────────────────────┘

Orchestrator → A2A → Critic Agent
                    Grounding / Constraint / Citation / Plan Evaluation
```

### 2.1 Agent 职责

| Agent | 设计范式 | 职责 | 权限 |
|---|---|---|---|
| Orchestrator Agent | Plan-and-Execute | 分解目标、生成计划、派发任务、动态重规划、汇总结果 | 只能调用其他 Agent，不直接访问数据库 |
| Ticket Agent | ReAct | 查询车站、直达票、替代日期、替代站和一次中转方案 | 只读 MCP Tools |
| Policy RAG Agent | Corrective RAG | 回答退改签、学生票、儿童票、行李与乘车规则 | 只读知识库 |
| Critic Agent | Evaluator-Optimizer / Reflexion | 检查约束覆盖、事实依据、引用、幻觉和计划完成度 | 无业务写权限 |

购买动作仍由用户在前端确认后进入原 Java 购票链路，Agent 只返回可跳转的车次与查询条件。

## 3. Agent 规划与反思机制

### 3.1 Plan-and-Execute 状态

Planner 使用 Structured Output 生成计划，而不是自由文本：

```json
{
  "goal": "规划上海到成都的低价行程",
  "constraints": {
    "dateRange": ["2026-08-20", "2026-08-22"],
    "maxTransfers": 1,
    "maxPrice": 800
  },
  "steps": [
    {
      "id": "step-1",
      "agent": "ticket-agent",
      "action": "查询直达车票",
      "dependsOn": [],
      "successCriteria": "至少获得一条真实 ticketRef"
    }
  ]
}
```

Graph 主路径：

```text
load_memory
   → planner
   → dispatch_a2a
   → collect_artifacts
   → replan_if_needed
   → synthesize
   → critic
      ├─ accepted → persist_memory → END
      └─ rejected → planner（携带结构化反馈，最多重试 2 次）
```

每执行完一个步骤，Orchestrator 根据 Observation 更新 `step.status`：

- `COMPLETED`：满足该步骤成功条件；
- `NEED_MORE_INFO`：向用户追问必要约束；
- `REPLAN`：工具没有结果，需要尝试替代日期、车站或中转；
- `FAILED`：Agent/MCP 超时或返回不可恢复错误。

### 3.2 ReAct 专业 Agent

Ticket Agent 与 Policy RAG Agent 内部使用 ReAct：

```text
模型判断当前缺少什么信息
    → Function Calling 选择工具
    → MCP/RAG 执行
    → Observation 写回 Agent State
    → 模型继续调用工具或生成 Artifact
```

模型负责决策，工具负责真实数据访问。工具不替模型推荐，但必须执行硬约束校验。

### 3.3 Reflexion 如何运行

Critic Agent 不读取模型隐藏思维过程，只评估可观测轨迹：用户目标、计划、工具参数、工具返回、引用和最终答案。

Critic 输出：

```json
{
  "accepted": false,
  "scores": {
    "constraintCoverage": 0.8,
    "groundedness": 1.0,
    "citationCorrectness": 0.6
  },
  "issues": ["学生票规则缺少有效来源"],
  "retryStrategy": "调用 policy-rag-agent 补充学生票证据"
}
```

反思循环：

1. `synthesize` 生成候选答案；
2. Critic 检查车次是否来自 `ticketRef`、用户约束是否全部覆盖、知识结论是否能映射到 Citation；
3. 不通过时把 `issues + retryStrategy` 写入 State；
4. Planner 只重做失败步骤，不重新运行整条链路；
5. 最多反思 2 次，仍失败则降级为“证据不足/暂时无法规划”，防止无限循环和成本失控；
6. 将失败轨迹压缩为“场景、动作、错误、修正策略、结果”写入 Episodic Memory，供以后相似任务召回。

## 4. 多 Agent 与 A2A 协议

### 4.1 为什么使用 A2A

A2A 用于独立 Agent 之间的协作，MCP 用于 Agent 与工具/数据源之间的交互，二者职责不同：

```text
Orchestrator Agent ──A2A──> Ticket Agent ──MCP──> Java Ticket Tools
Orchestrator Agent ──A2A──> Policy Agent ───────> Qdrant Retriever
```

每个远程 Agent 暴露 Agent Card，描述自身 URL、认证方式、流式能力和 Skills。Orchestrator 启动时发现 Agent Card，再通过 A2A 创建 Task。

### 4.2 A2A 数据设计

- 使用 `contextId` 关联同一轮行程规划；
- 使用 `taskId` 标识一次专业 Agent 任务；
- 请求使用结构化 DataPart，避免靠自然语言解析 Agent 间参数；
- 返回 Artifact，例如 `TicketSearchArtifact`、`PolicyEvidenceArtifact`；
- 长任务使用 SSE 返回 TaskStatus 和 Artifact 增量；
- 透传 `traceId`、超时时间、幂等键和用户身份指纹；
- Agent Card 不保存明文密钥，服务间采用 JWT/OAuth2 鉴权。

### 4.3 失败策略

- A2A 超时：重试一次，之后返回 Orchestrator 重规划；
- MCP 失败：Ticket Agent 返回结构化错误，不编造数据；
- 部分任务成功：Orchestrator 可以基于已有 Artifact 输出降级答案；
- Critic 不可用：执行规则校验器，检查引用、`ticketRef` 和必填约束。

## 5. 记忆系统

### 5.1 记忆分类

| 类型 | 内容 | 存储 | 作用域 |
|---|---|---|---|
| Working / Short-term | 当前消息、计划、约束、工具观察、反思次数 | LangGraph State + Redis Checkpointer | 单个 `threadId` |
| Semantic Memory | 常用出发地、席别偏好、预算、是否接受中转 | MySQL Profile + Qdrant 向量 | 用户跨会话 |
| Episodic Memory | 历史任务的动作、错误、结果和修正经验 | MySQL 原文 + Qdrant 摘要向量 | 用户或 Agent |
| Procedural Memory | 中转规划、规则问答、故障恢复步骤 | Agent Skills Git 版本库 | Agent 共享 |

### 5.2 短期记忆

LangGraph State 保存：

```text
messages / current_plan / constraints / observations
retrieved_evidence / agent_artifacts / critic_feedback / retry_count
```

Redis Checkpointer 以 `userFingerprint + threadId` 为 Key 保存状态，使用滑动 TTL。每个 Graph Node 完成后创建 checkpoint，因此进程重启或 A2A 暂时失败后可以从最近节点恢复。

### 5.3 长期记忆写入

主请求完成后异步执行 Memory Consolidator：

1. 从对话中提取稳定事实、用户偏好和可复用经验；
2. Pydantic 校验结构，过滤 Token、身份证等敏感内容；
3. 与已有记忆做语义相似度去重；
4. MySQL 保存结构化事实和原始审计记录；
5. BGE-M3 生成记忆向量并写入 Qdrant；
6. 保存 `userId/type/importance/createdAt/lastAccessedAt/sourceThreadId` 等元数据。

每轮开始只召回 Top 3-5 条与当前任务相关的记忆，并结合相关度、时间衰减和重要度进行重排，不把全部历史塞给模型。

### 5.4 上下文过长如何压缩

触发条件采用双阈值：消息超过 16 条，或估算 Token 达到模型上下文窗口的 60%。

压缩规则：

1. 永久保留 System Prompt、当前计划、未解决约束、最近 8 条消息和最近一次工具结果；
2. 将更早消息总结成结构化 `ConversationSummary`：

```json
{
  "stableFacts": [],
  "preferences": [],
  "decisions": [],
  "openQuestions": [],
  "toolEvidenceRefs": [],
  "failedAttempts": []
}
```

3. 摘要与原始消息分别存储：摘要进入上下文，原文保留在 MySQL 供审计；
4. 多个旧摘要再次进行分层合并，删除重复和已失效偏好；
5. 工具返回只保留结构化字段和引用 ID，大型原始结果存对象/数据库，通过 ID 按需读取；
6. 摘要后运行一致性检查，确保日期、车站、预算和未解决问题没有丢失。

## 6. Function Calling、MCP 与 Agent Skills

### 6.1 Function Calling

Function Calling 是模型输出结构化动作的机制，用于：

- 选择本地工具；
- 生成 Planner 的结构化计划；
- 选择要调用的 A2A Agent；
- 输出 Critic 的结构化评分；
- 校验参数类型和必填字段。

### 6.2 MCP

Ticket Agent 通过 MCP Client 发现并调用 Spring AI MCP Server 提供的只读工具：

- `search_stations`
- `search_tickets`
- `get_train_timetable`
- `get_seat_inventory_snapshot`

MCP Server 不暴露 `create_order`、`deduct_inventory` 或 `pay`，把 Agent 并发与核心抢票链路隔离。用户确认购买后由前端调用 Java Gateway。

### 6.3 Agent Skills

Skill 是按需加载的流程知识，不等同于 Tool。每个 Skill 使用标准目录：

```text
skills/
├── transfer-planning/
│   ├── SKILL.md
│   └── references/transfer-rules.md
├── policy-qa/
│   ├── SKILL.md
│   └── references/citation-format.md
├── preference-aware-ranking/
│   └── SKILL.md
└── agent-failure-recovery/
    └── SKILL.md
```

系统启动时只加载 Skill 的名称和描述。命中具体场景后再加载完整 `SKILL.md`，需要时才读取 references，从而减少 Prompt 长度。Skill 可以声明允许使用的工具，并通过 Git 进行版本化和评审。

## 7. RAG 设计

### 7.1 文档处理与切分

知识源包括退改签规则、学生票/儿童票规则、行李规定、乘车须知和运营公告。

入库流水线：

```text
Load → OCR/Parse → Clean → Structure-aware Split
     → Metadata Enrichment → Embedding → Qdrant Upsert
```

采用“结构感知 + Parent-Child”切分：

- Parent Chunk：800-1200 tokens，保留完整章节，用于最终提供上下文；
- Child Chunk：250-400 tokens，用于高精度召回；
- Overlap：40-60 tokens；
- FAQ 的问题与答案作为一个整体；
- 表格保留表头并按逻辑行分组，不直接按字符截断；
- 每个 Child 前补充 `文档标题 > 章节 > 小节`，减少脱离上下文；
- Metadata 保存规则类型、适用人群、生效时间、版本、来源和 parentId。

语义被切断时的处理顺序：

1. 优先按 Markdown 标题、段落、句号递归切分；
2. 使用 Overlap 保留相邻指代；
3. Child 命中后返回对应 Parent；
4. 对超长复杂段落使用 Semantic Chunker，根据相邻句 Embedding 距离寻找主题边界；
5. 对“本条/上述/以下条件”等强指代文本，自动携带前一段或所属条款。

Chunk 大小不是固定真理。250-400 tokens 是初始值，最终使用 Recall@K、Context Precision、延迟和 Token 成本在 200/300/400/500 tokens 的实验中选择。

### 7.2 Embedding 是什么

Embedding 把文本映射为高维向量，使语义相近的文本在向量空间中距离更近。常见路线包括：

- Word2Vec、GloVe：静态词向量，同一个词在不同上下文中向量不变；
- BERT：上下文表征，但原始 BERT 不适合直接做句向量检索；
- SBERT、SimCSE：通过孪生网络或对比学习优化句向量；
- DPR、E5、BGE：面向检索任务训练的 Bi-Encoder；
- SPLADE/BGE Sparse：学习稀疏词项权重，擅长专有名词和精确匹配；
- ColBERT：多向量 Late Interaction，效果更细但存储和计算成本更高。

本项目选择 **BGE-M3**：

- 对中文和多语言友好；
- 输出 1024 维 Dense Vector；
- 同时支持 Dense、Sparse 和 Multi-vector；
- 最大输入长度 8192 tokens；
- 可以自部署，避免票务知识发送到外部 Embedding API；
- 使用同系列 `bge-reranker-v2-m3` 做 Cross-Encoder 重排。

### 7.3 向量数据库选择

| 数据库 | 优点 | 不足 | 结论 |
|---|---|---|---|
| pgvector | 与 PostgreSQL 共用，事务和 SQL 过滤方便 | 混合检索和多向量能力需要较多自建逻辑 | 适合当前基础版 |
| Elasticsearch/OpenSearch | BM25 和过滤成熟 | 向量、多阶段检索配置更复杂 | 适合全文检索主导场景 |
| Milvus | 大规模向量检索和索引能力强 | 个人项目运维较重 | 暂不选择 |
| Qdrant | 原生 Dense/Sparse Named Vector、Metadata Filter、RRF 和多阶段查询 | 需要增加独立服务 | **Agent 2.0 选择** |

TrainMind 的知识规模不大，选择 Qdrant 不是因为数据量，而是为了用一个检索服务清晰展示 Dense/Sparse Hybrid Search、过滤、融合与重排流程。

### 7.4 检索优化流程

```text
Query Classification
   ├─ 实时余票/价格 → MCP Tool，不进入 RAG
   └─ 票务规则问题
         → Query Rewrite（原问题 + 1-2 个改写）
         → Metadata Filter（规则类型/人群/生效时间）
         → BGE-M3 Dense Top20
         → BGE-M3 Sparse Top20
         → RRF Fusion Top15
         → bge-reranker-v2-m3 Top5
         → Parent Expansion + 去重
         → Relevance Threshold
         → LLM Grounded Answer + Citation
```

优化点：

- 专有名词、车次号和规则编号依赖 Sparse Retrieval；
- 口语化问题依赖 Dense Retrieval；
- RRF 避免直接混合不同量纲的原始分数；
- Cross-Encoder 只重排少量候选，平衡效果与延迟；
- 根据评估集调整 Top-K、Chunk Size、RRF 权重和 Threshold；
- 对多意图问题拆分子查询，分别检索后去重合并。

### 7.5 幻觉规避

1. 实时余票、价格和订单状态只能来自 MCP，禁止从 RAG 或记忆推断；
2. RAG 回答必须返回 `documentId/section/effectiveDate/citation`；
3. 检索低于阈值时回答“证据不足”，不让模型凭常识补全；
4. 将知识文档视为不可信数据，清洗 Prompt Injection，并用标签隔离 Evidence；
5. Critic 将答案拆成 Claims，逐条检查是否存在 Evidence 或 Tool Observation；
6. 对规则版本按生效时间过滤，发现冲突时展示冲突而不是擅自选择；
7. 工具结果使用 Pydantic Schema 校验，车次引用必须命中真实 `ticketRef`。

## 8. 效果量化与评估

### 8.1 数据集

建设 300 条离线评估集：

- 100 条直达、替代日期、替代站和中转规划；
- 100 条退改签、学生票、儿童票、行李规则问答；
- 50 条多轮偏好与记忆测试；
- 30 条 MCP/A2A 故障恢复测试；
- 20 条 Prompt Injection、过期规则和无答案测试。

每条样本保存标准工具轨迹、相关文档、参考答案、必要约束和禁止行为。

### 8.2 指标

| 层级 | 指标 |
|---|---|
| Retrieval | Recall@5、MRR@10、nDCG@10、Context Precision、Context Recall |
| Generation | Faithfulness、Answer Relevancy、Answer Correctness、Citation Precision |
| Agent | Tool Call Accuracy/F1、Agent Goal Accuracy、Plan Completion Rate、Constraint Satisfaction Rate |
| Multi-Agent | A2A Task Success Rate、重试率、Artifact 完整率、Reflection Recovery Rate |
| Memory | Preference Recall、错误记忆率、压缩后关键信息保留率 |
| System | P50/P95 延迟、模型 Token、单请求成本、MCP/A2A 错误率 |

初始目标（是验收目标，不写成已经取得的结果）：

- Retrieval Recall@5 ≥ 0.90；
- Faithfulness ≥ 0.90；
- Tool Call Accuracy ≥ 0.95；
- Constraint Satisfaction Rate ≥ 0.95；
- Citation Precision ≥ 0.95；
- 无依据断言率 ≤ 2%；
- 普通查询 P95 ≤ 8 秒，多 Agent 复杂规划 P95 ≤ 20 秒。

使用 RAGAS 评估 Faithfulness、Context Precision/Recall、Tool Call 和 Agent Goal，使用 LangSmith 保存 Graph/A2A/MCP 全链路 Trace并进行离线回归与线上抽样评估。

## 9. 推荐实施顺序

### 阶段 A：单 Agent 深化

- 增加 Planner/Replanner 和 Critic 节点；
- 使用 Redis Checkpointer；
- 实现结构化摘要压缩和长期记忆写入；
- 保留现有 MCP Tools。

### 阶段 B：RAG 2.0

- 引入 BGE-M3、Qdrant 和 Parent-Child Chunk；
- 实现 Dense/Sparse + RRF + Reranker；
- 建立 RAGAS 离线数据集与指标基线。

### 阶段 C：多 Agent 与 Skills

- 拆分 Ticket、Policy 和 Critic Agent；
- 暴露 Agent Card 并接入 A2A；
- 编写中转规划、规则问答和故障恢复 Skills；
- 增加 A2A 超时、幂等和降级机制。

### 阶段 D：工程化

- LangSmith/OpenTelemetry Trace；
- Prompt、模型、Chunk 和检索参数版本管理；
- 离线回归、线上抽样评估和成本监控。

## 10. 当前代码与目标架构差距

| 能力 | 当前状态 | 2.0 目标 |
|---|---|---|
| Agent | 单 ReAct Agent | Planner + 专业 Agent + Critic |
| Agent 通信 | 进程内调用 | A2A 1.0 |
| 工具 | MCP 查站/查票 | 保留并扩展只读工具 |
| 短期记忆 | Redis/MySQL 消息持久化 | LangGraph Checkpointer + 摘要压缩 |
| 长期记忆 | 历史会话恢复 | Semantic/Episodic Memory + Qdrant |
| RAG | 关键词 + 可选 pgvector | BGE-M3 + Qdrant Hybrid + Reranker |
| 反思 | 基础工具校验 | Critic + Reflexion 闭环 |
| Skills | 无 | 标准 `SKILL.md` 能力包 |
| 评估 | 单元测试 | RAGAS + LangSmith + 业务指标 |

## 11. 官方资料

- [LangGraph Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [LangGraph Workflows and Agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [A2A Protocol 1.0](https://a2a-protocol.org/v1.0.0/)
- [MCP Architecture](https://modelcontextprotocol.io/specification/2025-06-18/architecture)
- [Agent Skills Specification](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx)
- [BGE-M3 Model Card](https://huggingface.co/BAAI/bge-m3)
- [Qdrant Hybrid Queries](https://qdrant.tech/documentation/search/hybrid-queries/)
- [RAGAS Metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/)
- [LangSmith RAG Evaluation](https://docs.langchain.com/langsmith/evaluate-rag-tutorial)
