# ADR-005: 任务轮询分发模型

## Status

Accepted

## Context

运维任务（服务检查/操作/日志）需下发到被监控服务器执行。Agent 位于 NAT/防火墙后，Backend 无法主动连接；需选择任务分发与结果回传方式。

## Decision

采用 **Agent 轮询分发**：

- Agent 每 `task_poll_interval`（默认 5s）`GET /agent/tasks/pending` 领取任务，服务端将执行置 RUNNING 并返回参数。
- Agent 执行后 `POST /agent/task/result` 回传，服务端更新执行/任务状态并写 `ops_task_log`。
- 任务状态机：CREATED → PENDING → RUNNING → SUCCESS/FAILED/TIMEOUT/CANCELLED；超时由调度器扫描置 TIMEOUT。
- 幂等：重复回传被拒绝；资产/服务同步为幂等 upsert。

## Alternatives

### WebSocket 推送

- 优点：实时下发。
- 缺点：连接维护复杂，NAT 下仍需 Agent 发起。

### 消息队列（如 RabbitMQ/Redis 队列）

- 优点：解耦、可靠投递。
- 缺点：引入额外中间件，运维成本上升。

### 长轮询

- 优点：降低空轮询。
- 缺点：连接占用与超时处理更复杂。

## Consequences

### Positive

- 契合 Agent 主动出站模型，无需 Backend 直连。
- 实现简单，易于扩展多服务器与批量任务。

### Negative

- 任务下发存在轮询延迟（≤ 轮询周期）。
- 需处理超时与重复回传。
- CRON 任务当前为单次触发，周期性多轮执行受唯一约束限制，需后续 schema 迭代。
