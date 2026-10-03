# Ops Monitor 优化路线图

> 本文规划 Ops Monitor 的工程化演进方向。与 `TODO.md` 的分工：`TODO.md` 记录**文档欠账**，本文记录**工程优化路线**（含代码、CI、可观测性、安全）。两者重叠的条目以本文为准，`TODO.md` 仅保留文档类引用。

## 0. 修订记录

- 本路线图合并了三份外部优化建议：初版《项目优化方案》、校准版《Ops Monitor 优化实施计划》、以及《任务重试策略》设计稿。
- 所有条目均以**当前代码为事实来源**重新核对，已实现项不重复排期，与现状不符的表述已修正（见 §4、§5）。
- 任务重试的详细设计见 [`architecture/task-retry-strategy.md`](architecture/task-retry-strategy.md)。

## 1. 编写原则

1. **以当前代码为事实来源**：每项结论均给出文件/行号证据，不按“计划中的设计”臆测。
2. **区分已完成与未完成**：避免把已实现能力列为待办，浪费排期。
3. **信息不足标注 `TODO`**：无法从代码确认的内容不进行推测性补全。
4. **中文正文、英文文件名**：遵循 `docs/README.md` 的文档规则。
5. **小步提交，单一职责**：每个 Commit 只解决一个问题。

## 2. 现状快照

以下能力**已经实现**，是后续优化的基线（证据为当前代码）：

| 能力 | 证据 |
| --- | --- |
| Agent 双运行时（Python / Go） | `agent/`、`agent-go/`、ADR-007 |
| Agent 注册 / 心跳 / 指标 / 资产 / 服务上报 | `backend/app/api/v1/agent.py` |
| Agent Token 哈希存储（SHA-256 + 前缀） | `backend/app/services/server_service.py:87`、`agent_service.py:59`、ADR-003 |
| Agent 传输层指数退避重试（无次数上限、无 jitter） | `agent/reporter/client.py:76`、`agent-go/internal/reporter/client.go` |
| 指标采集与查询（latest / history / summary） | `backend/app/api/v1/monitor.py` |
| 指标生命周期清理 | `METRIC_RETENTION_DAYS=7`、`backend/app/core/scheduler.py`（`_cleanup_old_metrics`） |
| 告警规则 + 状态机（PENDING/FIRING/ACKNOWLEDGED/RESOLVED） | `backend/app/models/alert.py`、`services/alert_engine.py` |
| 告警去重（`alert_key` 指纹）与恢复（`recovery_threshold`） | `alert_engine.py:40`、`models/alert.py` |
| 告警持续时长（`duration_seconds`） | `models/alert.py`、`alert_engine.py:149` |
| 服务管理（白名单受控启停 / 日志） | `backend/app/services/task_service.py`（`_validate_service_whitelist`） |
| 任务单机/批量/定时（CRON）+ 状态机 + 超时扫描 | `task_service.py`、`scheduler.py`（`_scan_task_timeouts`、`_fire_due_cron_tasks`） |
| 用户 JWT 认证、RBAC、操作审计 | `api/v1/auth.py`、`roles.py`、`users.py`、`middleware/operation_log.py` |
| 健康检查 `/health`（DB + Redis，503 语义） | `backend/app/api/v1/health.py` |
| CI（backend / agent / agent-go / frontend） | `.github/workflows/ci.yml` |
| 镜像发布与 Go Agent Release | `.github/workflows/publish.yml`、`release-agent.yml` |
| 文档体系 + 7 篇 ADR | `docs/`、`docs/decisions/` |
| Agent 一键安装脚本与包下载 | `backend/app/api/v1/agent.py`（`/install.sh`、`/package`） |
| 测试 | 后端 21 个测试文件、`agent/tests/`、`agent-go` 内 `_test.go` |
| 部署健康检查与重启策略 | `deploy/docker/compose.yml` |

## 3. 真实缺口与优先级

### P0：低成本、高收益

| 编号 | 缺口 | 证据 |
| --- | --- | --- |
| P0-1 | 缺少 `LICENSE` | 仓库根无 `LICENSE`；`README.md` 标注“许可证待定” |
| P0-2 | 缺少数据库 Migration | 无 `alembic` 依赖；Schema 唯一来源为 `deploy/mysql/init/ops_monitor_schema.sql`；CI 用正则剥离 `CREATE DATABASE` 后执行（`ci.yml:54`） |
| P0-3 | 缺少代码质量门禁 | 无 `ruff` / `mypy` / `pytest-cov`；无 pytest 配置文件；CI 仅跑测试与构建 |

### P1：工程可靠性

| 编号 | 缺口 | 证据 |
| --- | --- | --- |
| P1-4 | 后端日志非结构化 | 使用 stdlib `logging` 文本格式；`request_id` / `user_id` 已注入 `request.state`（`middleware/request_context.py`）但未进入日志记录 |
| P1-5 | 任务无重试 / 退避 / 幂等 | `task_service.py` 仅有 `scan_timeouts`；无 `attempt` / `max_attempts` / `retry_delay` / `Idempotency-Key`（全仓 grep 无匹配）。注意：Agent 已有**传输层**重试，缺的是**服务端任务级**重试 |
| P1-6 | Redis 未实际用于业务 | 仅出现在 `core/config.py`、`api/v1/health.py`；无缓存 / 分布式锁 / 限流实现 |
| P1-7 | 前端无测试与 lint | `frontend/package.json` 脚本仅 `dev` / `build` / `preview`；devDependencies 无 vitest / eslint |

### P2：可观测性、安全与高级能力

| 编号 | 缺口 | 证据 |
| --- | --- | --- |
| P2-8 | 无 Prometheus `/metrics` | 全仓无 prometheus 客户端依赖与端点 |
| P2-9 | 无 OpenTelemetry | 全仓无 otel 依赖 |
| P2-10 | Agent 请求无签名 / 防重放 / 限流 | 仅 Bearer Token（ADR-003）；无 `timestamp` / `request_id` / HMAC 签名。且后端只存 token 哈希，无法用 token 验签（见 §5 P2-10） |
| P2-11 | 容器无资源限制 | `deploy/docker/compose.yml` 有 healthcheck / restart，无 `deploy.resources` / `mem_limit` / `cpus` |
| P2-12 | 备份与恢复未确认自动化 | 已有文档 `operations/backup.md`、`operations/recovery.md`；是否脚本化并演练需核对（TODO） |
| P2-13 | 无 Server Discovery | 无网络扫描 / 批量注册实现 |
| P2-14 | 无高可用 / 多实例 | 当前为单实例部署；任务领取未做跨实例互斥；Scheduler 每实例各自运行 |
| P2-15 | 无性能压测 | 无 Locust / k6 / pytest-benchmark 基线 |

## 4. 实施阶段与依赖

```text
Phase 1（P0，本轮）
  License
     ↓
  Alembic（必须先行，后续所有 schema 变更走迁移）
     ↓
  Ruff / MyPy / Coverage

Phase 2（P1，本轮）
  Structured Logging
     ↓
  Task Retry（模型 + 错误分类）→ Task Retry（调度 + deadline）→ Idempotency
     ↓
  Agent 网络重试（次数上限 + jitter）
     ↓
  Frontend Test / Lint

Phase 3（P2 可观测性 / 安全，后续）
  Prometheus → OpenTelemetry → Agent 请求签名 → 容器资源限制

Phase 4（高级能力，后续）
  备份自动化 → 高可用（Redis 分布式锁 + Scheduler 选主）→ Server Discovery → 性能压测
```

**关键顺序约束**：

- Alembic 基线必须先于 P1-5 的任何加列，保证 `0002` 差异有可靠基准。
- Agent 请求签名（P2-10）需先确定**独立签名密钥**的下发方式，才能动检索接口。
- Redis 分布式锁的唯一价值是**多实例互斥**，因此并入 Phase 4（P2-14），不作为独立 P1 项。

## 5. 分阶段实施

### P0-1：新增 LICENSE（Apache-2.0）— 已完成

- **目标**：确定并落盘项目许可证。
- **做法**：新增根 `LICENSE`（Apache-2.0 全文）；更新 `README.md` License 段；在 `docs/reference/license-inventory.md` 记录结论；勾除 `docs/TODO.md` 对应项。
- **验收**：`LICENSE` 存在；GitHub 识别许可；markdownlint / lychee 通过。
- **涉及**：`LICENSE`、`README.md`、`docs/reference/license-inventory.md`、`docs/TODO.md`。

### P0-2：引入 Alembic 数据库迁移 — 已完成

- **目标**：Schema 演进不再依赖手工执行 SQL。
- **现状**：唯一来源 `deploy/mysql/init/ops_monitor_schema.sql`（MySQL 容器首启执行）；CI 正则剥离建库语句后执行（`ci.yml:54`）；`Dockerfile.backend:20,31` 仅 `COPY app` 并以 `uvicorn --workers 2` 启动。
- **做法**：
  1. 引入 `alembic` 依赖，新增 `backend/alembic.ini`、`backend/migrations/env.py`（import 全部 models、读 `settings.database_url`）、`backend/migrations/versions/`。
  2. **在真实 SQL 建出的 Schema 上 `--autogenerate` 生成 `0001_initial`，并验证 `diff = 0`**；不得为让 Alembic 通过而手工改写基线模型或迁移文件。
  3. 新增 `entrypoint.sh`：先 `alembic upgrade head` 再 exec uvicorn（避免 2 workers 并发迁移）；`Dockerfile.backend` 补 `COPY alembic.ini migrations`。
  4. 移除 `compose.yml` 的 init 挂载并**删除** `deploy/mysql/init/ops_monitor_schema.sql`。
  5. CI 去掉正则 bootstrap，改为执行迁移。
  6. 存量库在升级文档中说明 `alembic stamp 0001_initial` 对齐。
- **验收**：空库 `alembic upgrade head` 后可完整启动；`alembic downgrade -1` 可回滚；对已升级库再次 autogenerate `diff = 0`；CI 绿。
- **涉及**：`backend/requirements.txt`、`backend/alembic.ini`、`backend/migrations/`、`deploy/docker/Dockerfile.backend`、`deploy/docker/compose.yml`、`deploy/mysql/init/`、`.github/workflows/ci.yml`、`docs/operations/upgrade.md`。
- **ADR**：`008-database-migration-strategy`。

### P0-3：建立代码质量门禁 — 已完成

- **目标**：PR 阶段拦截风格、类型与覆盖率回退。
- **做法**：
  1. 新增 `backend/requirements-dev.txt`（`ruff`、`mypy`、`pytest-cov`）与 `backend/pyproject.toml`（ruff / mypy / pytest / coverage 配置）。
  2. mypy 先宽松（`ignore_missing_imports`、非严格），逐步收紧；覆盖率门槛从低起步。
  3. CI 新增 `quality` job：`ruff check`、`mypy app`、`pytest --cov=app`。
- **验收**：CI 对新增风格/类型错误失败；产出覆盖率报告。
- **涉及**：`backend/pyproject.toml`、`backend/requirements-dev.txt`、`.github/workflows/ci.yml`。

### P1-4：后端结构化日志 — 已完成

- **目标**：日志可被采集与检索，自动携带请求上下文。
- **现状**：stdlib `logging` 文本；`request_id` / `user_id` 在 `request_context.py` 中已注入 `request.state`，但未进入日志。
- **做法**：引入 JSON formatter + 基于 `contextvars` 的 filter，自动注入 `request_id`、`user_id`（`trace_id` 预留）；统一字段 `timestamp/level/service/request_id/trace_id/user_id/agent_id/action/message/error`。
- **验收**：单条日志为 JSON；同一请求的日志带相同 `request_id`；新增单测。
- **涉及**：`backend/app/core/logging.py`（新增）、`middleware/request_context.py`、`main.py`。

### P1-5：任务重试、退避与幂等 — 已完成

> 详细设计见 [`architecture/task-retry-strategy.md`](architecture/task-retry-strategy.md)。核心原则：**合并策略，不合并实现；分层重试，职责分离，总预算约束。**

- **目标**：任务失败可控重试，重复提交不重复执行。
- **现状**：仅有超时扫描；**每次 target 只有一条 execution**（`ops_task_execution` 唯一键 `(task_id, target_id)`）；Agent 传输层重试已存在但无次数上限 / jitter。
- **关键修正**：派发为 **Agent 轮询领取**（`fetch_pending`，`task_service.py:160`），不存在 `CLAIMED` / `DISPATCHING` 状态；重试发生在 **execution（attempt）级**，聚合态由 `_aggregate_task_status` 派生。
- **做法**（拆 3 步）：
  1. **模型与错误分类**（迁移 `0002`）：`ops_task` 加 `max_attempts`、`attempt`、`deadline_at`、`idempotency_key`（唯一）；`ops_task_execution` 加 `attempt`、`next_retry_at`、`error_type`，唯一键改为 `(task_id, target_id, attempt)`（**每次 attempt 新建一条 execution**）。错误分类映射到 `exceptions/error_codes.py`；`TaskResultRequest` 增加可选 `error_type`，Python/Go Agent 上报，服务端兜底分类。
  2. **重试调度**：`report_result` 失败按分类 / 剩余次数 / `deadline_at` 决定 `RETRYING + next_retry_at` 或终态 `FAILED/DEAD`；新增 `_dispatch_retries` 扫描到期项**新建 attempt**；`_aggregate_task_status` 改为按 target 取**最大 attempt** 的最新执行再汇总（历史 FAILED 不得污染结果）。
  3. **幂等**：`POST /tasks` 接受 `Idempotency-Key` 头，重复返回既有任务；`report_result` 对已结束执行由当前 400（`task_service.py:196`）改为**返回既有结果**，支持“Server 超时、Agent 后成功”。
- **验收**：可重试错误按退避重试并收敛；不可重试错误不重试；同幂等键不重复建任务；同 `execution_id` 重复回传不重复执行；批量 / CRON 聚合正确。
- **涉及**：`backend/app/models/task.py`、`repositories/task_repository.py`、`services/task_service.py`、`schemas/task.py`、`schemas/agent.py`、`api/v1/tasks.py`、`core/scheduler.py`、迁移脚本、双 Agent。
- **ADR**：`009-task-retry-and-idempotency`。

### P1-6：明确 Redis 职责（本轮不实施）

- **目标**：让 Redis 承担缓存、分布式锁、限流等职责。
- **现状**：仅配置项与健康检查使用。
- **修正**：分布式锁**并入 Phase 4（P2-14）**，作为多实例任务领取协调的前置；本轮仅在文档登记，不实现。
- **涉及（后续）**：`backend/app/core/`、`services/task_service.py`。

### P1-7：前端测试与 lint — 已完成

- **目标**：前端纳入质量门禁。
- **做法**：引入 `vitest` + `@vue/test-utils` + `jsdom` + `eslint`（+ `eslint-plugin-vue`）；`package.json` 增加 `lint` / `test`；CI frontend job 增加 lint / test（保留 build）；首批覆盖 store（`theme.js`）、utils（`clipboard.js` 等）。
- **验收**：本地与 CI `npm run lint`、`npm run test` 通过。
- **涉及**：`frontend/package.json`、`frontend/` 测试与 lint 配置、`.github/workflows/ci.yml`。

### P2-8：Prometheus 指标 — 已完成

- **目标**：Backend 暴露 `/metrics` 供抓取。
- **做法**：引入 `prometheus-client`；先暴露 `ops_agent_up`、`ops_alert_firing_total`、`ops_task_execution_total`、`ops_task_execution_duration_seconds` 等；`/metrics` 需访问控制；避免高基数标签（勿用 `task_id` / `execution_id` / `request_id` / `trace_id` / `user_id`）。
- **验收**：Prometheus 可抓取；指标与业务一致。

### P2-9：OpenTelemetry（拆分范围）— 后端链路已完成

- **目标**：建立 Trace 定位瓶颈。
- **修正**：拆为两部分——**可交付**：前端 → Nginx → FastAPI → MySQL/Redis → Task 派发；**可选后置**：Agent 归因（通过请求头透传 `trace_id` 并在 Agent 日志记录，不强制 Agent 内置 OTel SDK）。
- **依赖**：P1-4 结构化日志（`trace_id`）。
- **验收**：后端请求链路可查看完整耗时分解。

### P2-10：Agent 请求签名与防重放（Ed25519）— 已完成

- **目标**：Agent 高权限接口具备完整性与防重放保护。
- **关键修正**：ADR-003 仅存 `SHA-256(token)`（`server_service.py:87`），**后端无法用 Bearer Token 验签**。必须下发**独立签名密钥**（库中存哈希），Agent 配置保存明文。
- **做法**：注册 / 安装时下发签名密钥；请求头增加 `X-Agent-ID`、`X-Timestamp`、`X-Request-ID`、`X-Signature`；签名 `HMAC-SHA256(secret, method+path+timestamp+request_id+body)`；后端校验顺序 Token → Timestamp → Request ID → Signature，并配合限流。
- **验收**：篡改或重放请求被拒绝；重复 `request_id` 被拒。
- **涉及**：`server_service.py::generate_agent_token`、`/install.sh`、`api/v1/agent.py`、`services/agent_service.py`、双 Agent 配置 schema。
- **ADR**：`010-agent-request-signing`（设计已产出，待实现）。

### P2-11：容器资源限制 — 已完成

- **目标**：防止单服务耗尽宿主资源。
- **做法**：`compose.yml` 为各服务补充 `deploy.resources.limits`（或 `mem_limit` / `cpus`）与日志轮转配置。
- **验收**：容器受限于设定上限。

### P2-12：备份与恢复自动化 — 已完成

- **目标**：备份可执行、可恢复、可演练。
- **现状**：文档已有流程（`operations/backup.md`、`operations/recovery.md`）。
- **做法**：确认是否已脚本化；补充定时备份与恢复演练清单。
- **验收**：定期备份产出并在独立环境成功恢复；数据完整性验证通过。

### P2-13：Server Discovery

- **目标**：CIDR 扫描 → 探测 → 安装 Agent → 注册上线。
- **备注**：涉及网络扫描与凭据管理，高风险，需单独安全设计，排在 Phase 4。

### P2-14：高可用 / 多实例 — 调度协调与多副本已完成

- **目标**：Backend 无状态化、任务跨实例互斥。
- **前置**：P1-6 的 Redis 分布式锁在本阶段落地；Scheduler 选主 / 协调（当前每实例各跑告警评估、CRON、清理）。
- **做法**：Redis 锁 + Scheduler 协调；Redis HA、MySQL 主从；Agent 重连策略。
- **验收**：多实例下任务不重复执行、告警不重复触发。
- **ADR**：`012-distributed-task-lock`。

### P2-15：性能压测

- **目标**：在真实数据量下定位瓶颈。
- **做法**：引入 Locust / k6，覆盖 API、指标写入、任务吞吐、告警评估延迟；记录 P50/P95/P99 基线；产出至 `benchmarks/reports/`。

## 6. 推荐提交序列

```text
docs: merge plans and add task retry strategy
docs: add Apache-2.0 LICENSE
chore: add alembic migrations and drop sql init
ci: add ruff mypy and coverage gates
observability: structured json logging
feat(task): per-attempt executions and error classification
feat(task): retry scheduling and deadlines
feat(task): idempotency key and result replay
feat(agent): bounded network retries with jitter
test(frontend): add vitest and eslint
docs: sync changelog and module docs
```

## 7. 验收标准

完成 P0 与 P1 后，应形成稳定闭环：

```text
监控
 ↓
发现问题
 ↓
触发告警（去重 / 持续时长）
 ↓
确认 / 恢复
 ↓
执行任务（重试 / 超时 / 幂等）
 ↓
Agent 返回结果
 ↓
问题恢复
 ↓
Alert Resolved
 ↓
Audit Log
```

完成 P0 后，新环境应满足：

```text
创建数据库
   ↓
alembic upgrade head
   ↓
启动系统（无需手工执行 SQL）
```

## 8. 维护约定

- 新增能力完成后，从本文对应条目标记移除，并在 `CHANGELOG.md` 记录。
- 重要技术选型（签名方案、迁移策略、可观测性栈、分布式锁）新增 ADR，位于 `docs/decisions/`。
- 文档类欠账继续维护在 `TODO.md`，工程类欠账以本文为准。

## 9. 已确认决策与开放问题

### 已确认决策

| 决策 | 结论 |
| --- | --- |
| License | Apache-2.0 |
| 本轮范围 | Phase 1 + Phase 2 |
| Agent 签名密钥 | 独立签名密钥（注册 / 安装时下发） |
| Redis 分布式锁 | 并入 Phase 4（P2-14） |
| 重试记录模型 | 每次 attempt 新建一条 `ops_task_execution` |
| Agent 网络重试 | 增加 `max_retries` + jitter（双运行时） |
| MySQL init 脚本 | Alembic 落地后删除，单一来源 |
| 重试设计文档 | `docs/architecture/task-retry-strategy.md` |

### 开放问题

- `DEADLINE_EXCEEDED` 与 `TIMEOUT` 是否拆分为独立状态（在 ADR-009 中定义）。
- `network_retry_count` 是否落库（取决于 Agent 是否上报网络重试次数）。
- 多轮 CRON 任务与重试的交互边界（在 ADR-009 中定义）。
