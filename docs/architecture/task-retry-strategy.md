# 任务重试策略

> 本文定义 Ops Monitor 中 **Server 任务重试**与 **Agent 网络重试**的职责边界、状态模型、错误分类与预算约束。
>
> 核心原则：**合并策略，不合并实现；分层重试，职责分离，总预算约束。**
>
> 本文以当前代码为事实来源。任务派发为 **Agent 轮询领取**（pull），不是 Server 主动推送。

## 1. 目标

系统同时存在两类失败场景：

1. Agent 与 Server（或目标服务）之间**单次请求级**的瞬时通信失败。
2. 一个**业务任务**执行失败后，需要由 Server 重新调度。

这两类失败不能共用同一套计数器，也不能由同一层承担全部责任。

设计目标：

- Agent 负责短暂、瞬时、请求级网络问题。
- Server 负责任务级重新调度。
- 业务逻辑层判断错误是否允许重试。
- 所有重试受任务总体 deadline 约束。
- 每层维护独立计数器、日志与指标。
- 所有重试具备幂等性保护。

## 2. 分层职责

| 层级 | 负责内容 | 是否重试 | 示例 |
| --- | --- | --- | --- |
| Agent 网络层 | Agent 到 Server 的单次请求瞬时失败 | 是 | Connection reset、timeout、部分 5xx |
| Server 任务层 | 业务任务执行失败后的重新调度 | 是 | Agent 离线、执行超时、临时执行失败 |
| 业务逻辑层 | 判断错误是否值得重试 | 有限 | 权限不足、参数错误不重试 |

```text
Agent Retry  = 请求级重试
Server Retry = 任务级重试
```

两者不能混用。Server 不能因为 Agent 的一次网络抖动就创建新任务尝试，Agent 也不能自行决定业务任务是否重新执行。

## 3. 现状与差异（重要）

当前实现与常见“Server 推送”模型不同，重试设计必须基于**轮询**：

- 派发：Agent 调用 `fetch_pending`（`backend/app/services/task_service.py:160`）领取待执行任务，服务端把 execution 由 `PENDING` 置为 `RUNNING`。因此**不存在** `CLAIMED` / `DISPATCHING` 状态。
- 执行记录：`ops_task_execution` 目前每个 target 只有一条，唯一键为 `(task_id, target_id)`（见 `backend/app/models/task.py`）。
- 已有状态：
  - `ops_task`：`CREATED`（待二次确认）→ `PENDING` → `RUNNING` → `SUCCESS/FAILED/TIMEOUT/CANCELLED`（`models/task.py:24`）。
  - `ops_task_execution`：`PENDING` → `RUNNING` → `SUCCESS/FAILED/TIMEOUT/CANCELLED`（`models/task.py:90`）。
- 聚合：`_aggregate_task_status`（`task_service.py:296`）由执行结果派生任务状态。
- Agent 网络重试：已存在但为**时间封顶（默认 60s）指数退避，无次数上限、无 jitter**（`agent/reporter/client.py:76`、`agent-go/internal/reporter/client.go`）。

据此，本设计需要新增 `RETRYING` / `DEAD` 状态，并把唯一键改为包含 `attempt`（每次尝试新建一条 execution）。

## 4. 推荐执行流程

```text
Server 创建任务
    ↓
Task PENDING（高风险操作先经 CREATED 确认）
    ↓
Agent 轮询 fetch_pending 领取（PENDING → RUNNING）
    ↓
Agent 网络重试 ≤ max_retries
    ├── 成功 → Agent 执行 → 回传结果
    │
    └── 仍失败
          ↓
      本次 attempt 标记 FAILED
          ↓
      Server 依据 error_type 判断是否重试
          ↓
      RETRYING（记录 next_retry_at）
          ↓
      等待 backoff
          ↓
      Server 新建下一次 attempt（PENDING）
          ↓
      Agent 再次领取
```

## 5. 三层重试模型

```text
┌────────────────────────────────────┐
│ Server Task Retry                  │
│ max_attempts = 3                   │
│ backoff = 5s / 10s / 30s           │
└────────────────┬───────────────────┘
                 ▼
┌────────────────────────────────────┐
│ Agent Request Retry                │
│ max_retries = 2~3                  │
│ short backoff + jitter             │
└────────────────┬───────────────────┘
                 ▼
┌────────────────────────────────────┐
│ Actual Task Execution              │
│ 受控动作：STATUS/START/STOP/...    │
└────────────────────────────────────┘
```

### 第一层：Server Task Retry

- 新建下一次任务尝试（新 execution 行）。
- 控制任务级 `max_attempts`。
- 计算任务级 backoff。
- 依据错误分类判断是否重试。
- 受任务整体 `deadline_at` 约束。
- 维护任务状态机与审计记录。

推荐配置：

```yaml
task:
  max_attempts: 3
  backoff:
    type: exponential
    initial: 5s
    max: 60s
```

### 第二层：Agent Request Retry

- 处理单次 HTTP 请求的瞬时失败。
- 使用短退避 + 随机抖动。
- 超过次数后返回明确错误。
- 不决定业务任务是否重新执行。

推荐配置（在现有时间封顶基础上增加次数上限与 jitter）：

```yaml
agent_request:
  max_retries: 2
  timeout: 10s
  backoff:
    type: exponential
    initial: 500ms
    max: 3s
    jitter: true
```

### 第三层：Actual Task Execution

- 执行受控动作，例如 `STATUS`、`START`、`STOP`、`RESTART`、`LOGS`。
- 返回明确结果、退出码与错误分类。
- 不自行为无限重试，遵守幂等与超时约束。

## 6. 避免重试风暴

若简单嵌套 `Server 3 次 × Agent 3 次 = 9 次`，再叠加其它重试会导致请求膨胀。

约束原则：

```text
不要共享计数器
不要无限嵌套重试
不要对所有失败无条件重试
不要忽略任务总 deadline
不要让网络重试变成业务重试
```

## 7. 任务总体时间预算

即使两层各自独立，也必须受统一 deadline 限制。

```yaml
task:
  timeout: 300s
```

规则：`Server Retry × Agent Retry` 不能突破任务整体 deadline。创建下一次业务尝试前，Server 必须检查：

```text
当前时间 + 预计退避 + 预计执行 < task.deadline_at
```

预算不足则不再新建 attempt，进入终态。

> **TODO**：`DEADLINE_EXCEEDED` 与 `TIMEOUT` 是否拆分为独立状态，在 ADR-009 中统一定义。

## 8. 数据模型

### `ops_task`（新增字段）

```text
max_attempts     允许的最大任务尝试次数
attempt          当前 / 最近一次尝试编号
deadline_at      任务整体截止时间
idempotency_key  防止重复创建业务任务（唯一约束）
```

### `ops_task_execution`（新增字段，每次 attempt 一行）

```text
attempt          任务级尝试编号
next_retry_at    下次重试时间（重试调度扫描条件）
error_type       标准化错误类型
```

现有字段保留：`status`、`exit_code`、`result_text`、`error_message`、`started_at`、`finished_at`、`duration_ms`。

唯一键由 `(task_id, target_id)` 改为 `(task_id, target_id, attempt)`。

### 关键约束

```text
ops_task.attempt            ≠  Agent 网络重试次数
ops_task_execution.attempt  =  Server 任务级尝试编号
```

不新增 `stdout` / `stderr` 列：执行输出沿用 `result_text` 与 `ops_task_log`。

## 9. 错误分类与重试决策

不要使用 `if status == "FAILED": retry()`。按错误类型决定是否新建业务 attempt，并映射到现有 `backend/app/exceptions/error_codes.py`。

### 可重试

```text
NETWORK_ERROR
AGENT_OFFLINE
AGENT_TIMEOUT
SERVER_5XX
```

### 不可重试

```text
INVALID_ARGUMENT
PERMISSION_DENIED
COMMAND_NOT_FOUND
SERVICE_NOT_WHITELISTED
TASK_ACTION_INVALID
```

### 条件重试

```text
AGENT_EXECUTION_TIMEOUT
SERVICE_UNHEALTHY
DEPENDENCY_UNAVAILABLE
RESOURCE_EXHAUSTED
```

例如 `restart_service` 超时后不应立刻重复执行，应先查询服务实际状态再决定。

> **TODO**：`error_type` 的完整枚举与到 `ErrorCode` 的映射表在实现阶段补充，并由 `TaskResultRequest`（`schemas/agent.py:94`）扩展可选 `error_type`，双 Agent 上报，服务端按 `error_message` 兜底分类。

## 10. 幂等性

### 创建任务幂等

请求携带 `Idempotency-Key`：

```text
第一次请求 → 创建 Task
相同 Key 再次请求 → 返回已有 Task
```

并发场景用唯一约束保证，冲突时读取既有记录返回。

### Agent 执行幂等

Server 调度时携带稳定标识 `task_id` / `execution_id` / `attempt`。Agent 应能识别重复执行：

```text
相同 execution_id 已完成 → 返回已保存结果
相同 execution_id 执行中 → 返回当前状态或拒绝重复执行
```

服务端 `report_result`（`task_service.py:181`）当前对已结束执行返回 400（`task_service.py:196`），应改为返回既有结果，从而支持“Server 超时、Agent 后成功”的恢复。

## 11. 日志与审计

日志必须区分任务级与请求级重试。建议字段：

```text
task_id, execution_id, attempt, network_retry,
agent_id, request_id, trace_id, error_type,
retryable, next_retry_at, deadline_at
```

任务状态变化写入审计，事件名：

```text
TASK_CREATED, TASK_CLAIMED, TASK_RUNNING, TASK_ATTEMPT_FAILED,
TASK_RETRY_SCHEDULED, TASK_SUCCEEDED, TASK_DEAD, TASK_TIMEOUT, TASK_CANCELLED
```

> 说明：`TASK_CLAIMED` 对应现有的“Agent 轮询领取”动作。

## 12. Prometheus 指标

任务级与网络级独立统计：

```text
ops_task_attempt_total
ops_task_retry_total
ops_task_failure_total
ops_task_dead_total
ops_task_timeout_total
ops_task_execution_duration_seconds

ops_agent_network_retry_total
ops_agent_request_failure_total
ops_agent_request_duration_seconds
```

标签建议：`task_type`、`action`、`agent_id`、`error_type`、`status`、`retryable`。

禁止高基数标签：`task_id`、`execution_id`、`request_id`、`trace_id`、`user_id`。

## 13. 状态模型

### Task 状态（聚合，由 `_aggregate_task_status` 派生）

```text
CREATED（待二次确认）
   ↓ 确认
PENDING
   ↓
RUNNING
   ├── SUCCESS
   ├── FAILED
   ├── TIMEOUT
   ├── CANCELLED
   └── RETRYING
           ↓
        PENDING
```

最终不可恢复状态：`SUCCESS`、`FAILED`、`TIMEOUT`、`CANCELLED`、`DEAD`。

### Execution（attempt）状态

```text
PENDING
   ↓ 领取
RUNNING
   ├── SUCCESS
   ├── FAILED
   ├── TIMEOUT
   ├── CANCELLED
   └── RETRYING
           ↓
        PENDING（新 attempt）
```

> **TODO**：`FAILED`、`TIMEOUT`、`DEAD`、`DEADLINE_EXCEEDED` 的最终语义与流转关系在 ADR-009 中明确。

## 14. 实施顺序

```text
1. 定义错误码与错误分类
    ↓
2. 扩展 Task 与 Execution 数据模型（Alembic 0002）
    ↓
3. 增加 max_attempts、backoff 与 deadline
    ↓
4. 实现 Idempotency-Key
    ↓
5. 实现 Agent 请求级短重试（max_retries + jitter）
    ↓
6. 实现 Server 任务级重试调度（_dispatch_retries）
    ↓
7. 补充审计日志与结构化日志
    ↓
8. 暴露 Prometheus 指标
    ↓
9. 增加 Unit、Integration 与 E2E 测试
```

> Redis 分布式锁（多实例任务领取协调）**不在本阶段**，归入高可用（参考 [`../optimization-plan.md`](../optimization-plan.md) P2-14）。

## 15. 验收标准

职责边界：

```text
[ ] Agent 网络重试与 Server 任务重试使用独立计数器
[ ] Agent 网络重试不直接创建新的任务 attempt
[ ] Server 任务重试不复用 Agent 网络重试计数
[ ] 所有业务重试由错误分类决定
```

时间与容量保护：

```text
[ ] 每个任务具备整体 deadline
[ ] 新 attempt 不得突破 deadline
[ ] Agent 请求重试使用短退避与 jitter
[ ] Server 任务重试使用任务级 backoff
[ ] 重试达到上限后进入最终状态
```

幂等性：

```text
[ ] 相同 Idempotency-Key 不创建重复 Task
[ ] 相同 execution_id 不在 Agent 上重复执行
[ ] Server 超时后可查询 Agent 既有执行结果
```

可观测性：

```text
[ ] 日志包含 task_id、execution_id、attempt 与 network_retry
[ ] 任务级与网络级重试指标独立统计
[ ] 审计日志可还原任务状态流转
```

## 16. ADR

```text
docs/decisions/
├── 008-database-migration-strategy.md
├── 009-task-retry-and-idempotency.md
└── 010-structured-logging.md
```

优先记录决策：

1. Server 任务重试与 Agent 网络重试分层实现。
2. 任务级与请求级计数器不共享。
3. 任务整体 deadline 约束所有重试行为。
4. 错误分类决定业务重试资格。
5. Agent 基于 `execution_id` 保证执行幂等。
6. 每次 attempt 新建 execution 行（便于审计）。
