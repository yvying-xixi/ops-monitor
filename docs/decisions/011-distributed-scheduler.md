# ADR-011: 分布式调度协调

## 状态

Accepted（已实现）

## 背景

后台调度器（APScheduler `BackgroundScheduler`）在应用 lifespan 中启动。当前 backend 以
`uvicorn --workers 2` 运行，**每个 worker 进程都会执行 lifespan 并启动一个调度器**，
即单容器内存在两个调度器；若进一步水平扩展为多实例，重复度更高。

涉及的调度作业：Agent 状态刷新、告警评估、CRON 触发、任务超时扫描、重试派发、
指标清理、任务历史清理。多数作业近似幂等，但重复执行造成资源浪费，并在并发下产生竞态。

同时，nginx 以 `proxy_pass http://backend:8000` 在启动时解析单一容器 IP，无法支持 backend 多副本。

## 问题

在单容器多 worker 与多实例部署下，保证每个调度作业每轮只被执行一次；并让入口支持 backend 水平扩展。

## 选项

### A. 每作业 Redis 锁（选择）

每个作业每轮尝试 `SET sched:lock:<job> <token> NX PX <ttl>`；抢到才执行，执行完用
比较并删除（Lua）释放；TTL 作为进程崩溃时的兜底。

- 优点：实现简单；无需额外进程；对 2 worker 与 N 实例一致；执行完立即释放，不影响下一周期。
- 缺点：依赖 Redis；TTL 需大于最长执行时间。

### B. 单进程调度 + 独立 worker 容器

将调度器拆到单独进程/容器，Web worker 不启动调度。

- 优点：语义清晰。
- 缺点：部署复杂度上升；仍需处理该进程的高可用（选主）。

### C. 数据库咨询锁 / APScheduler 持久化 JobStore

- 优点：不依赖 Redis。
- 缺点：MySQL 咨询锁跨连接语义复杂；持久化 JobStore 仍需选主，改造大。

## 决策

采用 **A. 每作业 Redis 锁**：

- `backend/app/core/scheduler_lock.py`：`scheduler_lock(job, ttl)` 上下文管理器与 `run_with_lock()`。
- `scheduler.py`：以 `@_locked("<job>")` 装饰所有作业，未获锁则跳过本轮。
- 配置：`SCHEDULER_LOCK_ENABLED`（默认 `true`）、`SCHEDULER_LOCK_TTL_SECONDS`（默认 600）。
- Redis 异常时**跳过本轮**并记录，不惊群、不放行。
- 释放采用 Lua 比较并删除，避免误删他人的锁。

### 多实例入口

- nginx 增加 `resolver 127.0.0.11 valid=10s` + 变量式 `proxy_pass`，运行时解析 `backend`，配合
  Docker DNS 支持 `docker compose up --scale backend=N`。

## 备选方案

见 Options。

## 影响

### 正面

- 修复「2 worker 重复调度」，并支持 backend 水平扩展。
- 实现轻量，无新增常驻进程。

### 负面

- 强依赖 Redis（异常时调度暂停，但 Web 接口不受影响）。
- 作业执行时间不得超过 TTL，否则锁提前过期可能并发执行（当前作业均为秒级）。
- **Redis / MySQL 仍是单点**：真 HA 需外部托管/集群，超出本 ADR 范围。

## 待决问题

- 长任务是否需要锁续租（当前不需要）。
- 是否需要「选主 + 集中调度」替代「每作业锁」以降低 Redis 调用量。
- 调度暂停告警：是否需要接入平台自身告警通道。
