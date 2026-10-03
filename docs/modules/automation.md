# 自动化任务

> 本文描述任务引擎：任务创建、分发、执行与状态聚合。

## 总体机制

```mermaid
flowchart LR
    subgraph 服务状态
        A1[Agent systemctl 采集] --> A2[POST /agent/services] --> A3[ops_server_service]
    end
    subgraph 运维操作
        B1[后端建任务] --> B2[Agent 轮询领取] --> B3[受控执行] --> B4[回传结果] --> B5[状态聚合]
    end
```

### 任务分发（Agent 轮询）

```mermaid
sequenceDiagram
    participant BE as Backend
    participant AG as Agent
    participant EX as Executor
    BE->>BE: 创建 ops_task + targets + executions
    loop 每 task_poll_interval(5s)
        AG->>BE: GET /agent/tasks/pending
        BE-->>AG: execution_id/action/service/timeout（PENDING→RUNNING）
        AG->>EX: 白名单二次校验后执行
        EX-->>AG: 结果
        AG->>BE: POST /agent/task/result
        BE->>BE: 更新状态 + 写 ops_task_log
    end
```

## 任务模型与状态机

```mermaid
stateDiagram-v2
    [*] --> CREATED: 需确认
    CREATED --> PENDING: 确认
    [*] --> PENDING: 免确认
    PENDING --> RUNNING: Agent 领取
    RUNNING --> SUCCESS
    RUNNING --> RETRYING: 可重试失败
    RETRYING --> RUNNING: 调度器派发下一次尝试
    RETRYING --> DEAD: 重试耗尽 / 超过 deadline
    RUNNING --> FAILED: 不可重试失败
    RUNNING --> TIMEOUT: 超时扫描 30s
    CREATED --> CANCELLED: 取消
    PENDING --> CANCELLED: 取消
```

- `task.status` 由 executions 聚合：按每个 target 的**最新 attempt** —— 任一 RETRYING→RETRYING；任一活跃→RUNNING；任一 DEAD→DEAD；任一 FAILED/TIMEOUT→FAILED；全 SUCCESS→SUCCESS。
- 批量任务：每台服务器独立 execution，前端展示独立结果。

### 重试与幂等

- 每次尝试独立成行（`(task_id, target_id, attempt)`），失败尝试进入 `RETRYING`，调度器每 5s 派发到期的下一次尝试。
- 错误分类见 `app/core/retry.py`：仅网络/Agent 离线/Agent 超时/5xx 等可重试；参数/权限/白名单类错误不重试；未知错误默认不重试。
- 任务预算：`max_attempts` 与 `deadline_at = created_at + timeout_seconds × max_attempts`。
- 幂等：创建任务可带 `Idempotency-Key` 请求头；Agent 重复回传同一 `execution_id` 时返回既有结果。
- 详见 [architecture/task-retry-strategy.md](../architecture/task-retry-strategy.md) 与 [decisions/009-task-retry-and-idempotency.md](../decisions/009-task-retry-and-idempotency.md)。

### 任务类型

| task_type | action | 说明 |
| --- | --- | --- |
| SERVICE_CHECK | STATUS | 服务状态检查（只读） |
| SERVICE_ACTION | START/STOP/RESTART | 受控操作，默认需二次确认 |
| SERVICE_LOG | LOGS | 日志抓取 |

## 定时任务（CRON）

- `schedule_type=CRON` + `cron_expression`（5 字段）。
- 创建即 CREATED，确认后 PENDING；调度器每 30s 用 croniter 计算到期，触发时生成执行批次。
- **当前为单次触发**：执行完成后任务结束；周期性多轮执行需后续任务行级 schema 迭代（`ops_task_execution` 唯一约束为 `(task_id, target_id, attempt)`）。

## 任务 API

| Method | Endpoint | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/tasks` | 任务分页列表 | admin/ops |
| POST | `/api/v1/tasks` | 创建任务（单机/批量/定时） | admin/ops |
| GET | `/api/v1/tasks/{id}` | 详情（各服务器执行结果+日志） | admin/ops |
| POST | `/api/v1/tasks/{id}/confirm` | 二次确认 | admin/ops |
| POST | `/api/v1/tasks/{id}/cancel` | 取消 | admin/ops |
| GET | `/api/v1/agent/tasks/pending` | Agent 轮询领取 | Agent Token |
| POST | `/api/v1/agent/task/result` | Agent 回传结果 | Agent Token |

## 前端

`views/task/index.vue`：任务中心（列表/新建/确认/取消/详情含各服务器执行日志）。

## 相关决策

- [decisions/005-task-polling-dispatch.md](../decisions/005-task-polling-dispatch.md)
