# TrainMind MCP Tools

独立的 Spring Boot 3.4 + Spring AI 1.0 MCP Server。它只暴露只读票务工具，
不提供下单、扣库存、支付或取消订单能力。

## 工具

- `search_stations`：搜索真实车站；
- `search_tickets`：按日期和可选起终点查询真实车次及余票。

## 启动

先启动 Business 服务，然后执行：

```powershell
mvn -f agent-tools/pom.xml spring-boot:run
```

或打包后启动：

```powershell
mvn -f agent-tools/pom.xml -DskipTests package
java -jar agent-tools/target/agent-tools-0.1.0-SNAPSHOT.jar
```

默认端口为 `8011`，MCP SSE 地址为：

```text
http://127.0.0.1:8011/sse
```

Business 地址可以通过环境变量覆盖：

```powershell
$env:TRAINMIND_BUSINESS_BASE_URL="http://127.0.0.1:18002"
```
