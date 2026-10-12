# Train 项目面试复习指南

这份指南用于快速找回项目记忆，并把项目整理成面试时能讲清楚的材料。建议先按“项目一句话、架构、核心购票链路、并发一致性、可改进点”这条主线复习，不要一上来陷入所有 CRUD 细节。

## 1. 项目定位

一句话介绍：

> Train 是一个仿 12306 的前后端分离火车票系统，后端采用 Spring Boot / Spring Cloud 微服务架构，覆盖会员登录、乘车人管理、车次与座位维护、每日车次生成、余票查询、选座购票、排队出票、定时任务和后台管理。

面试时可以强调的关键词：

- 微服务拆分：`gateway`、`member`、`business`、`batch`、`common`、`generator`
- 高并发购票：Redis 秒杀令牌、RocketMQ 排队削峰、按车次加锁串行出票、Sentinel 限流
- 数据一致性：Seata 全局事务，座位、余票、会员车票、订单状态一起提交或回滚
- 业务复杂度：区间余票、位图选座、每日车次数据生成、Quartz 持久化任务
- 工程效率：MyBatis Generator + 自定义 FreeMarker 模板生成 CRUD 和管理页

## 2. 项目模块怎么讲

| 模块 | 职责 | 面试讲法 |
| --- | --- | --- |
| `gateway` | 统一入口、路由转发、跨域、JWT 校验 | 外部请求统一走 8000，根据 `/member/**`、`/business/**`、`/batch/**` 转发到对应服务 |
| `member` | 会员、乘车人、已购车票 | 登录后签发 JWT；出票成功后由 business 通过 Feign 写入会员车票 |
| `business` | 核心业务服务 | 车站、车次、车厢、座位、每日车次、余票、确认订单、秒杀令牌、选座出票 |
| `batch` | 定时任务 | Quartz 持久化任务，调用 business 生成 15 天后的每日车次数据 |
| `common` | 公共能力 | 统一响应、异常、JWT、拦截器、日志切面、分页请求 |
| `generator` | 代码生成 | 生成 MyBatis 模型、Mapper、Service、Controller、后台 Vue 页面 |
| `web` | 用户端 | 登录、乘车人、查票、购票、订单轮询、我的车票 |
| `admin` | 管理端 | 基础数据维护、每日车次维护、订单查看、任务管理 |

## 3. 推荐复习顺序

### 第一步：先跑通脑图

先看这些文件：

- `README.md`
- `docs/architecture.svg`
- `pom.xml`
- `gateway/src/main/resources/application.properties`
- `business/src/main/resources/application.properties`
- `web/package.json`
- `admin/package.json`

你要能回答：

- 系统有哪些服务？
- 外部请求从哪里进来？
- 哪些服务依赖 MySQL、Redis、RocketMQ、Nacos、Seata、Sentinel？
- 用户端和管理端分别解决什么问题？

### 第二步：复习主业务链路

重点读：

- `business/src/main/java/com/jiawa/web/WebConfirmOrderController.java`
- `business/src/main/java/com/jiawa/service/Impl/BeforeConfirmOrderService.java`
- `business/src/main/java/com/jiawa/mq/ConfirmOrderConsumer.java`
- `business/src/main/java/com/jiawa/service/Impl/ConfirmOrderServiceImpl.java`
- `business/src/main/java/com/jiawa/service/Impl/AfterConfirmOrderService.java`
- `business/src/main/resources/mapper/cust/DailyTrainTicketMapperCust.xml`
- `business/src/main/java/com/jiawa/service/Impl/SkTokenServiceImpl.java`

你要能按下面顺序讲完整：

1. 用户在前端选择日期、车次、出发站、到达站、乘车人、座位类型，可选具体座位。
2. 请求进入 Gateway，非白名单接口需要校验 `token`。
3. business 接收 `/confirm-order/do` 请求，先做验证码和秒杀令牌校验。
4. 系统创建状态为 `INIT` 的确认订单。
5. 发送 RocketMQ 消息到 `CONFIRM_ORDER` 主题，实现排队削峰。
6. 消费者收到消息后，根据“日期 + 车次”加 Redis 锁，避免同一车次并发出票互相冲突。
7. 消费者分批取出 `INIT` 订单，逐条执行 `sell`。
8. `sell` 先预扣本次区间余票，再根据是否选座挑选实际座位。
9. 选座成功后进入 Seata 全局事务：更新座位售卖位图、更新受影响区间余票、调用 member 写入车票、更新确认订单为成功。
10. 前端轮询排队状态接口，根据返回值展示排队、成功、失败或无票。

## 4. 购票链路的面试讲述稿

可以这样讲：

> 这个项目里我把购票拆成了“下单前置校验”和“异步排队出票”两段。前置阶段主要解决入口压力和恶意请求问题：先通过 Gateway 做 JWT 校验，再通过验证码和 Redis 秒杀令牌控制能进入主流程的请求数量。校验通过后不直接出票，而是先创建一个 INIT 状态的确认订单，再发送 RocketMQ 消息。这样可以把瞬时高并发请求削峰成后台消费者可控的处理速度。
>
> 真正出票在消费者里完成。消费者按日期和车次加 Redis 锁，同一车次同一天只允许一个消费线程处理，避免座位和区间余票并发冲突。处理订单时先查出该起终点的余票，再根据座位售卖位图判断某个座位在站点区间内是否可售。如果用户选了座位，就用相对偏移保证多个乘客的座位组合符合用户选择；如果没选座，就按座位类型自动分配。
>
> 最后通过 Seata 全局事务把座位状态、区间余票、会员车票和订单状态放到一个事务里，任一步失败都回滚，保证跨服务数据一致性。

## 5. 核心技术点逐个复习

### 5.1 Gateway 和 JWT

源码：

- `gateway/src/main/java/com/jiawa/gateway/config/LoginMemberFilter.java`
- `common/src/main/java/com/jiawa/interceptor/MemberInterceptor.java`
- `common/src/main/java/com/jiawa/context/LoginMemberContext.java`
- `common/src/main/java/com/jiawa/util/JwtUtil.java`

要点：

- Gateway 做第一层认证，白名单包括登录、验证码、后台接口、测试接口等。
- 业务服务里通过拦截器从 token 解析会员信息，放入 `ThreadLocal` 上下文。
- Controller / Service 可以通过 `LoginMemberContext.getId()` 获取当前会员。

常见追问：

- 为什么 Gateway 校验后，业务服务还要解析 token？
- ThreadLocal 使用后是否需要清理？
- 当前白名单用 `path.contains()` 有什么风险？

回答方向：

- Gateway 负责拦截非法请求，业务服务解析 token 是为了拿当前登录用户上下文。
- ThreadLocal 在线程池环境下建议在请求结束后 remove，避免线程复用导致数据残留。
- `contains` 容易误放行，应改成精确路径匹配或 AntPathMatcher / Spring Security 规则。

### 5.2 秒杀令牌

源码：

- `business/src/main/java/com/jiawa/service/Impl/SkTokenServiceImpl.java`

作用：

- 令牌数量近似代表可进入购票主链路的请求量。
- Redis 缓存令牌数，用 `decrement` 原子扣减。
- 每个会员对同一日期车次加短 TTL 锁，降低同一用户重复抢票。
- 定期把 Redis 中的扣减结果批量同步回数据库。

面试要讲清楚：

- 令牌是入口削峰，不是最终库存一致性的唯一保障。
- 最终是否能买到票，还要靠座位位图和事务更新校验。
- Redis 令牌减少数据库压力，但要考虑缓存丢失、DB 同步延迟和负数回补问题。

### 5.3 RocketMQ 排队削峰

源码：

- `business/src/main/java/com/jiawa/service/Impl/BeforeConfirmOrderService.java`
- `business/src/main/java/com/jiawa/mq/ConfirmOrderConsumer.java`

要点：

- 用户请求先快速落订单，再进入 MQ。
- MQ 消费者异步出票，前端通过接口轮询状态。
- 这样避免所有请求同步占用业务线程和数据库连接。

常见追问：

- MQ 消息重复消费怎么办？
- 消息发送成功但订单创建失败怎么办？
- 订单状态为什么要有 `INIT`、`PENDING`、`SUCCESS`、`EMPTY` 等？

回答方向：

- 本项目用订单状态控制处理阶段，消费者只取 `INIT` 订单，处理前改成 `PENDING`，降低重复处理概率。
- 更严谨可以加唯一幂等表、消息 key、事务消息或本地消息表。
- 状态机用于支持排队查询、失败标记、无票结束和异常恢复。

### 5.4 Redis 锁和并发控制

源码：

- `business/src/main/java/com/jiawa/service/Impl/ConfirmOrderServiceImpl.java`

当前逻辑：

- 锁 key 由 `CONFIRM_ORDER + 日期 + 车次` 组成。
- 同一天同一车次只允许一个消费者批量出票。
- 每次分页取 5 条 `INIT` 订单，循环处理直到没有待处理订单。

可讲亮点：

- 锁粒度不是全局锁，而是按车次日期分段，减少互相影响。
- 订单异步排队，用户通过查询排队人数感知进度。

可讲改进：

- 当前代码用 Redis `setIfAbsent` 和手动 `delete`，如果处理时间超过 TTL，有提前释放风险。
- 更稳妥可以使用 Redisson `RLock` 自动续期，或确保消费耗时小于 TTL。
- 如果需要更高吞吐，可以按车次分区、顺序消息或更细粒度座位锁设计。

### 5.5 区间余票和位图选座

源码：

- `business/src/main/java/com/jiawa/service/Impl/DailyTrainTicketServiceImpl.java`
- `business/src/main/java/com/jiawa/service/Impl/ConfirmOrderServiceImpl.java`
- `business/src/main/java/com/jiawa/service/Impl/AfterConfirmOrderService.java`
- `business/src/main/resources/mapper/cust/DailyTrainTicketMapperCust.xml`

业务背景：

火车票不是简单库存。一个座位可以卖 A-B，也可以卖 B-C，但不能在重叠区间重复售卖。

本项目做法：

- 每个每日座位有 `sell` 字符串，表示各站点区间是否已售。
- 例如 `00000` 表示多个区间都未售，买某段后把对应区间改成 `1`。
- 判断可售：取 `sell.substring(startIndex, endIndex)`，如果全是 0，则这个座位在该区间可卖。
- 更新可售：构造本次购买区间的二进制位，与原 `sell` 做按位或。
- 更新余票：根据新售卖区间计算受影响的起止站范围，批量扣减对应区间余票。

面试讲法：

> 我没有把余票简单建成“车次 + 座位类型”的库存，因为火车票存在区间复用。项目里用座位 sell 位图表示每个座位在每段区间的占用状态，判断时只看本次起终点覆盖的区间是否全部未售。卖出后再反推出受影响的出发站和到达站范围，批量更新余票表。

### 5.6 Seata 分布式事务

源码：

- `business/src/main/java/com/jiawa/service/Impl/AfterConfirmOrderService.java`
- `business/src/main/java/com/jiawa/feign/MemberFeign.java`

事务内做了什么：

- 更新 `daily_train_seat.sell`
- 更新 `daily_train_ticket` 余票
- 调用 member 服务保存会员车票
- 更新 `confirm_order.status = SUCCESS`

面试要点：

- business 和 member 是两个服务，跨库更新需要分布式事务或最终一致性方案。
- 当前项目使用 Seata `@GlobalTransactional` 追求强一致。
- 也可以讨论替代方案：可靠消息最终一致性、本地消息表、TCC、Saga。

### 5.7 Sentinel 限流

源码：

- `BeforeConfirmOrderService.beforeDoConfirm`
- `ConfirmOrderServiceImpl.doConfirm`
- `business/src/main/resources/application.properties`

要点：

- `@SentinelResource` 给购票入口和出票处理加资源名。
- 限流触发后抛业务异常，前端可提示排队繁忙或稍后再试。
- 配置里接入了 Sentinel Dashboard 和 Nacos 动态规则。

面试追问：

- 限流放在哪里？
- 限流和令牌有什么区别？

回答方向：

- 限流控制系统吞吐，避免服务被打垮。
- 令牌控制业务资格，减少无效请求进入核心库存逻辑。

### 5.8 Quartz 每日车次生成

源码：

- `batch/src/main/java/com/jiawa/job/DailyTrainJob.java`
- `batch/src/main/java/com/jiawa/config/SchedulerConfig.java`
- `business/src/main/java/com/jiawa/service/Impl/DailyTrainServiceImpl.java`
- `business/src/main/java/com/jiawa/service/Impl/DailyTrainTicketServiceImpl.java`

流程：

1. Quartz 触发 `DailyTrainJob`。
2. Job 计算 15 天后的日期。
3. 通过 Feign 调用 business 生成每日车次。
4. business 基于基础车次生成每日车次、车站、车厢、座位、余票和秒杀令牌。

要点：

- 基础数据和每日数据分离，便于提前放票。
- `@DisallowConcurrentExecution` 避免同一 Job 并发执行。
- Quartz 配置了数据源，可以持久化任务。

## 6. 面试官最可能问的问题

### Q1：这个项目最大的难点是什么？

答：

> 最大难点是火车票的区间库存和高并发出票。普通商品只有一个库存，但火车票的一个座位可以在不重叠区间重复售卖，所以我用座位 sell 位图判断区间是否可售，并在出票后计算受影响的余票区间批量扣减。并发上通过 Redis 令牌挡掉大部分请求，用 RocketMQ 排队削峰，再按日期车次加锁串行处理核心出票，最后用 Seata 保证跨服务写入一致。

### Q2：如何防止超卖？

答：

> 第一层用秒杀令牌减少进入主流程的请求量；第二层消费者按日期车次加锁，避免同一车次并发改同一批座位；第三层选座时检查座位 sell 位图，只要目标区间有 1 就不能卖；最后更新座位、余票和订单在事务里完成。更严谨的生产方案还可以在 SQL 更新时增加版本号或条件更新，进一步防止异常并发导致覆盖。

### Q3：为什么要用 MQ？

答：

> 购票请求瞬时并发很高，如果同步出票，会把业务线程、数据库连接、锁资源全部压满。MQ 可以把用户请求快速变成确认订单，然后后台按能力消费。用户侧只需要轮询订单状态，这样系统吞吐更平滑，也方便做失败重试、排队展示和限流降级。

### Q4：如何保证 MQ 消费幂等？

答：

> 当前项目主要依赖订单状态机，消费者只处理 `INIT` 订单，处理前改成 `PENDING`，成功后改成 `SUCCESS`。如果消息重复到达，已经不是 `INIT` 的订单不会被重复取出。生产级可以继续加强，比如订单唯一约束、消费记录表、乐观锁更新状态、本地消息表或事务消息。

### Q5：Seata 在这里解决什么问题？

答：

> 出票成功要同时修改 business 库的座位和余票，又要调用 member 服务写入车票，还要更新订单状态。任何一步失败都会造成用户看到票但库存没扣、库存扣了但没车票等不一致。Seata 的全局事务把这些操作纳入同一个事务边界，失败时统一回滚。

### Q6：这个系统有什么不足？

可以主动说 3 到 5 个，不要说太多：

- Gateway 白名单用 `contains` 不够严谨，容易误匹配。
- ThreadLocal 登录上下文应在请求完成后清理。
- Redis 锁 TTL 固定，长任务可能超时释放，应使用 Redisson 看门狗或合理续期。
- MQ 幂等和异常恢复还可以加强，例如本地消息表、状态乐观锁。
- 管理端接口目前白名单放行较多，生产环境需要 RBAC 权限。
- 配置里有本地账号密码和密钥，生产应改为环境变量或配置中心密文。
- 自动化测试不足，购票和库存链路应补单元测试、集成测试和压测报告。

## 7. 代码走读路线

按这个顺序读，效率最高：

1. `gateway/src/main/java/com/jiawa/gateway/config/LoginMemberFilter.java`
2. `member/src/main/java/com/jiawa/controller/MemberController.java`
3. `business/src/main/java/com/jiawa/web/WebDailyTrainTicketController.java`
4. `business/src/main/java/com/jiawa/web/WebConfirmOrderController.java`
5. `business/src/main/java/com/jiawa/service/Impl/BeforeConfirmOrderService.java`
6. `business/src/main/java/com/jiawa/service/Impl/SkTokenServiceImpl.java`
7. `business/src/main/java/com/jiawa/mq/ConfirmOrderConsumer.java`
8. `business/src/main/java/com/jiawa/service/Impl/ConfirmOrderServiceImpl.java`
9. `business/src/main/java/com/jiawa/service/Impl/AfterConfirmOrderService.java`
10. `business/src/main/java/com/jiawa/service/Impl/DailyTrainServiceImpl.java`
11. `batch/src/main/java/com/jiawa/job/DailyTrainJob.java`
12. `web/src/views/main/ticket.vue`
13. `web/src/views/main/order.vue`

## 8. 简历写法参考

可以写成：

> 基于 Spring Boot 3、Spring Cloud、Vue3 实现仿 12306 火车票系统，负责购票核心链路设计与实现，包括余票查询、选座购票、秒杀令牌、MQ 排队出票、区间库存扣减和订单状态轮询。

> 使用 Redis 实现秒杀令牌和车次级出票锁，结合 RocketMQ 对高并发购票请求削峰；基于座位售卖位图实现区间余票判断，解决同一座位非重叠区间复用问题。

> 使用 Seata 管理出票过程中的跨服务事务，保证座位状态、余票、会员车票和订单状态一致；使用 Sentinel 对购票核心接口做限流降级。

> 使用 Quartz 持久化定时任务提前生成每日车次、座位、余票和秒杀令牌；使用 MyBatis Generator 与 FreeMarker 模板提升基础 CRUD 开发效率。

## 9. 三天复习计划

### 第一天：恢复项目整体记忆

- 看 `README.md`、架构图和模块目录。
- 画一张自己的请求链路图：浏览器 -> Gateway -> business/member/batch。
- 跑读登录、查票、购票三个入口。
- 整理一版 1 分钟项目介绍。

目标：

- 能说清楚系统是干什么的。
- 能说清楚为什么拆这些服务。
- 能说清楚外部依赖有哪些。

### 第二天：吃透购票核心

- 重点读 `BeforeConfirmOrderService`、`SkTokenServiceImpl`、`ConfirmOrderServiceImpl`、`AfterConfirmOrderService`。
- 手写一遍“购票 10 步流程”。
- 用例子解释 sell 位图：例如 5 个站点，买 1 到 4 后位图如何变化。
- 准备超卖、幂等、事务、限流、MQ 的追问回答。

目标：

- 面试官追问库存、锁、MQ、事务时能讲出实现细节。

### 第三天：准备亮点和不足

- 看 Quartz 每日车次生成。
- 看 Gateway 鉴权和 common 公共组件。
- 看前端购票页面和订单轮询。
- 准备“项目不足和改进方案”。
- 把简历项目描述背熟，避免和代码不一致。

目标：

- 能主动讲亮点，也能坦诚说出改进点。

## 10. 一分钟项目介绍

可以直接背：

> 这是一个仿 12306 的火车票购票系统，采用 Spring Boot 和 Spring Cloud 微服务架构，后端拆成网关、会员、业务、批处理和公共模块，前端有用户端和管理端。用户端支持登录、乘车人管理、余票查询、选座购票和订单状态查询；管理端支持车站、车次、车厢、座位、每日车次和定时任务管理。
>
> 项目核心是高并发购票链路。我用 Redis 秒杀令牌先控制进入购票主流程的请求量，再用 RocketMQ 把同步购票改成异步排队出票。消费者按日期和车次加锁，基于座位 sell 位图判断区间是否可售，出票成功后通过 Seata 全局事务同时更新座位、余票、会员车票和订单状态。批处理侧用 Quartz 提前生成每日车次、座位、余票和令牌数据。

## 11. 五分钟深度讲法结构

按这个顺序讲，不容易乱：

1. 业务背景：仿 12306，核心难点是区间余票和高并发抢票。
2. 架构拆分：Gateway、member、business、batch、common、前端双端。
3. 查询链路：用户查日期、起终点、车次，查 `daily_train_ticket`。
4. 下单链路：JWT、验证码、秒杀令牌、创建确认订单、发 MQ。
5. 出票链路：消费者拿消息、车次级锁、分批处理订单、选座、扣余票。
6. 一致性：Seata 包住座位、余票、会员车票、订单状态。
7. 可用性：Sentinel 限流、MQ 削峰、Redis 缓存、Quartz 预生成。
8. 不足改进：幂等、锁续期、权限、安全配置、测试覆盖。

## 12. 复习检查清单

面试前逐项确认：

- [ ] 能画出系统架构图。
- [ ] 能说出每个模块职责。
- [ ] 能从登录讲到 JWT 校验和会员上下文。
- [ ] 能完整讲出购票 10 步流程。
- [ ] 能解释 Redis 秒杀令牌的作用和不足。
- [ ] 能解释为什么用 MQ。
- [ ] 能解释订单状态机。
- [ ] 能解释车次级锁的粒度。
- [ ] 能解释 sell 位图如何判断区间可售。
- [ ] 能解释余票表为什么有起点和终点组合。
- [ ] 能解释 Seata 在这里保护哪些写操作。
- [ ] 能解释 Quartz 如何生成 15 天后的每日车次。
- [ ] 能说出 3 个项目亮点。
- [ ] 能说出 3 个项目不足和改进方案。
- [ ] 能把简历上的每个技术点对应到源码文件。

## 13. 建议优先补强的地方

如果面试前还有时间，可以优先做这些小修补或准备：

1. 补一张清晰架构图或流程图，面试时方便手画。
2. 给购票链路补一份压测结果说明，对应 `train.jmx`。
3. 准备 2 个具体例子说明 sell 位图。
4. 准备一次“如果让我重构”的回答：认证改 Spring Security，锁改 Redisson，幂等改状态乐观锁 + 消费记录表，事务根据场景从 Seata 改成本地消息表最终一致性。
5. 整理启动依赖：MySQL、Redis、Nacos、RocketMQ、Seata、Sentinel、前端端口。

## 14. 最值得背熟的源码位置

| 主题 | 文件 |
| --- | --- |
| 网关鉴权 | `gateway/src/main/java/com/jiawa/gateway/config/LoginMemberFilter.java` |
| 登录上下文 | `common/src/main/java/com/jiawa/interceptor/MemberInterceptor.java` |
| 秒杀令牌 | `business/src/main/java/com/jiawa/service/Impl/SkTokenServiceImpl.java` |
| 下单入队 | `business/src/main/java/com/jiawa/service/Impl/BeforeConfirmOrderService.java` |
| MQ 消费 | `business/src/main/java/com/jiawa/mq/ConfirmOrderConsumer.java` |
| 选座出票 | `business/src/main/java/com/jiawa/service/Impl/ConfirmOrderServiceImpl.java` |
| 分布式事务 | `business/src/main/java/com/jiawa/service/Impl/AfterConfirmOrderService.java` |
| 区间余票更新 | `business/src/main/resources/mapper/cust/DailyTrainTicketMapperCust.xml` |
| 每日车次生成 | `business/src/main/java/com/jiawa/service/Impl/DailyTrainServiceImpl.java` |
| 定时任务 | `batch/src/main/java/com/jiawa/job/DailyTrainJob.java` |

