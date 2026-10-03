# ADR-009: 任务重试与幂等

## Status

Accepted

## Context

任务执行存在两类失败：Agent 与 Server 之间的瞬时网络失败，以及业务任务执行失败后需要重新调度。原实现只有执行超时（`scan_timeouts`），没有任务级重试与幂等保护：

- 一个 target 只保留一条执行记录（唯一键 `(task_id, target_id)`），无法表达多次尝试。
- `POST /tasks` 无幂等键，网络重试可能创建重复任务。
- Agent 回传结果对已结束执行返回 400，无法应对“Server 超时但 Agent 后续成功”。

## Decision

- **分层重试，不共享计数器**：Agent 传输层负责单次请求的瞬时重试；Server 负责任务级重新调度。详见 [`../architecture/task-retry-strategy.md`](../architecture/task-retry-strategy.md)。
- **每次尝试新建执行记录**：`ops_task_execution` 唯一键改为 `(task_id, target_id, attempt)`；新增 `attempt`、`next_retry_at`、`error_type`。失败尝试进入 `RETRYING`，由调度器新建下一次尝试（`PENDING`）。
- **任务预算**：`ops_task` 新增 `max_attempts`、`attempt`、`deadline_at`。`deadline_at = created_at + timeout_seconds * max_attempts`；重试不得突破次数与 deadline。
- **错误分类**：`app/core/retry.py` 定义可重试 / 不可重试 / 条件重试错误。**未知错误默认不重试**，避免对参数/权限类错误反复执行。
- **幂等**：
  - 创建任务接受 `Idempotency-Key` 请求头，同键返回既有任务（唯一约束 `uk_ops_task_idempotency`）。
  - Agent 回传对已结束执行改为返回既有结果（幂等重放），不再报 400。
- **状态聚合**：`_aggregate_task_status` 改为按每个 target 的**最新 attempt** 汇总，历史失败不覆盖最新结果。

## Alternatives

### 直接复用一个执行记录并在其上递增 attempt

- 优点：改动小。
- 缺点：丢失每次尝试的独立记录，审计与排障困难；与“每次尝试一行”的验收标准冲突。

### 对所有 FAILED 无差别重试

- 优点：实现简单。
- 缺点：权限不足、参数错误等会反复执行，放大风险。故采用错误分类。

## Consequences

### Positive

- 可控重试与退避，避免重试风暴；任务总预算受约束。
- 幂等键与结果重放消除重复执行风险。
- 每次尝试可独立审计。

### Negative

- 执行记录数量随重试增长；已通过 `TASK_RETENTION_DAYS`（默认 30 天，每日清理终态执行与日志）控制。
- 条件重试错误仍按保守策略不重试。

## 状态语义与开放项

- **RETRYING**：本次失败已排定重试，等待调度器派发下一次尝试。
- **DEAD**：重试次数耗尽或整体 deadline 耗尽，重试不可恢复的终态。
- **FAILED**：不可重试错误的终态。
- **TIMEOUT**：执行超过 `timeout_seconds` 的终态；与是否可重试**解耦**，当前不重试。超时扫描按**各自任务**的 `timeout_seconds` 判定（`scan_timeouts`）。
- **DEADLINE_EXCEEDED**：不单独设状态。任务整体 `deadline_at` 耗尽时不再创建新尝试，当前执行进入 `DEAD`。
- **CRON × 重试**：每次到点触发一个执行批次；批次内失败按本策略重试，重试**不跨批次**（下一轮由新批次承担）。
