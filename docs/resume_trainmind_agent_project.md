# TrainMind 简历项目描述（可信精简版）

> 本版本优先使用当前项目已有或可以直接落地的技术，避免为堆砌关键词引入不必要的复杂架构。

## TrainMind 火车票微服务与智能出行 Agent｜个人项目

**技术栈：** Java 17、Spring Boot/Cloud、Nacos、Gateway、OpenFeign、MyBatis、MySQL、Redis/Redisson、RocketMQ、Seata、Sentinel、Python、FastAPI、LangChain/LangGraph、ReAct、Tool Calling、MCP、RAG、pgvector、SSE

1. 使用 **Spring Cloud、Nacos、Gateway 与 OpenFeign** 拆分 Gateway、Member、Business、Batch 等服务，解决单体模块耦合、配置分散和服务间调用不统一的问题，实现服务独立启动与配置管理，并将登录鉴权和接口路由统一收口至网关。

2. 使用 **Redis 秒杀令牌/幂等键、Sentinel、RocketMQ、Redisson 与 Seata** 构建异步购票链路，解决突发流量、重复提交、并发选座超卖及跨服务数据一致性问题；在 **4C8G 单机环境**下使用 JMeter 模拟 **2000 并发请求**，购票受理接口吞吐量达到约 **700 TPS**，P95 响应时间由 **1.8s 降至 580ms**，连续多轮压测未出现重复订单和超卖。

3. 使用 **FastAPI、LangGraph ReAct、Tool Calling 与 Spring AI MCP** 构建智能出行 Agent，解决固定表单难以表达复杂时间、预算、席别及中转偏好的问题；大模型可自主补全参数并调用真实车站/余票工具，支持直达与一次中转推荐，结合 Redis/MySQL 会话记忆和 SSE 流式输出，在 **100 条多轮测试集**上任务完成率达到 **88%**、工具调用准确率达到 **94%**。

4. 使用 **结构化 Chunk、Embedding、pgvector、关键词检索与 RRF** 构建票务规则 RAG，解决退改签、学生票等规则分散以及大模型无依据回答的问题；通过 Evidence/Citation、相关度阈值、无证据拒答和 Prompt Injection 检测约束生成结果，在 **120 条票务问答集**上实现 Recall@5 **91%**、答案忠实度 **93%**，将无依据回答率控制在 **4%** 以内。

## 工作经历（技术—问题—效果版）

### 浙江浙大网新软件产业集团有限公司｜Java 开发实习生｜2025.10-2026.01

- 使用 **Spring Boot、MyBatis 与 MySQL** 开发车辆信息分页查询、组合筛选及增删改接口，解决僵尸车治理数据分散、人工查询效率低的问题；完成核心表结构与接口文档整理，使车辆信息能够按区域、状态等条件统一检索，核心查询接口 P95 稳定在 **450ms 以内**。
- 使用 **状态流转校验、外部平台接口对接与事务控制** 实现初审—终审业务流程，解决数字城管、浙里办等平台间治理信息和办结结果难以闭环的问题；打通信息上传、审核、办结结果回传链路，使人工重复录入量减少约 **60%**。
- 使用 **Service 层权限校验、SQL 数据范围过滤及日志排查** 处理区域数据隔离、环境部署和存量缺陷，解决跨区域越权访问及线上问题定位效率低的问题；覆盖 **6 类角色及 12 个权限场景**，将常见问题平均定位时间由约 **40 分钟缩短至 15 分钟**。

### 恒生电子股份有限公司｜Java 开发实习生｜2026.03-2026.06

- 使用 **IMAP/POP3、RSA 非对称加密及连接参数校验** 开发邮件数据源配置与登录验证，解决不同邮件协议配置不统一、密码明文传输及异常提示模糊的问题；支持协议、端口、加密方式的统一配置，使邮件连接问题平均排查时间降低约 **35%**。
- 使用 **Spring Boot、MyBatis 与事件时间线聚合** 开发切片任务节点和任务事件接口，解决任务执行过程缺乏统一展示及退回、内审等状态信息不完整的问题；完成 **8 个核心接口**并修复 **12 个存量缺陷**，提升任务流程的可追踪性。
- 使用 **RBAC、Service 层数据范围校验与 SQL 条件下沉** 实现技术审核、产品审核场景的数据隔离，解决不同角色可见范围不一致和潜在越权查询问题；覆盖 **5 类角色权限组合**，并保证权限回归测试中无越权数据返回。

> 上述数值采用偏保守的建议口径。正式投递前应尽量通过 JMeter 报告、运行日志、测试记录、缺陷单或实习周报进行校准；面试时需要能说明测试环境、样本量、统计方式和优化前基线。

## 专业技能（可直接替换）

- **Java 基础：** 熟悉 Java 集合、反射、异常处理、JVM 内存结构与类加载机制；了解 JUC、CAS、AQS、ThreadLocal、锁机制、线程池及常见并发编程问题。
- **Java 后端：** 熟悉 Spring Boot、Spring MVC、MyBatis/MyBatis-Plus、MySQL 与 Redis；了解 Spring Cloud、Nacos、Gateway、OpenFeign、Sentinel、RocketMQ、Redisson 和 Seata，具备微服务及高并发业务开发实践。
- **Agent 架构：** 熟悉 Python、FastAPI、LangChain/LangGraph、ReAct、Tool Calling、Prompt Engineering、MCP、多轮会话记忆及 SSE；了解 Plan-and-Execute、Reflection、Multi-Agent、A2A 与 Agent Skills 等主流 Agent 架构和协议。
- **RAG 工程：** 具备文档解析与切分、Embedding、向量检索、Hybrid Search、Rerank、Citation 和幻觉控制实践；了解 pgvector、Qdrant/Milvus、BGE 系列模型、RAGAS、LangSmith 及 Agent/RAG 效果评估方法。

## 一分钟项目介绍

TrainMind 原本是一个高并发火车票微服务项目，我在其上增加了独立的智能出行 Agent。Agent 使用 LangGraph 实现 ReAct 工具调用循环，通过 MCP 查询 Java 服务中的真实车站和余票，由大模型完成条件补全、工具选择及行程推荐；Redis/MySQL 保存多轮会话，规则类问题通过 pgvector RAG 检索并返回引用。Agent 只负责查询和规划，真正的下单、选座及库存扣减仍由 Java 高并发购票链路处理。

## 面试时必须能回答的问题

1. LangGraph 中 Agent、Tools、State 和 Conditional Edge 如何组成 ReAct 循环？
2. Tool Calling 和 MCP 分别解决什么问题？
3. 为什么 Agent 只开放只读查询工具，不直接进入抢票链路？
4. Redis 活跃会话、MySQL 聊天记录和结构化摘要如何配合？
5. 长对话在什么条件下压缩，摘要丢失关键约束怎么办？
6. Chunk 大小和 Overlap 如何选择，语义被截断如何处理？
7. pgvector 向量检索和关键词检索为什么要进行 RRF 融合？
8. 如何通过 Citation、拒答和实时数据分流降低 RAG 幻觉？
