# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格。

## [Unreleased]

### Added

- 平台自有 Prometheus 指标端点 `GET /metrics`（`ops_agent_status`、`ops_server_total`、`ops_alert_active`、`ops_task_status`），支持 `METRICS_ENABLED` / `METRICS_TOKEN` 控制。
- 后端 OpenTelemetry 链路追踪（`OTEL_ENABLED` / `OTEL_SERVICE_NAME` / `OTEL_EXPORTER_OTLP_ENDPOINT`）：FastAPI / SQLAlchemy / Redis 自动埋点，`trace_id` 注入结构化日志。
- 部署容器资源上限（CPU/内存）与 json-file 日志轮转（`compose.yml`）。
- 新增 [ADR-010](docs/decisions/010-agent-request-signing.md)：Agent 请求签名（Ed25519）与防重放设计（待实现）。

### Changed

- 前端网关抖动重试：带 `Idempotency-Key` 的 POST 与幂等 GET 均可安全重试（此前仅 GET）。
- 任务历史保留扩展：同时清理过期的终态单次任务及其目标（保留 CRON 调度定义）。

## [0.3.0] - 2026-10-03

### Added

- 任务执行保留策略：`TASK_RETENTION_DAYS`（默认 30 天）与每日清理终态执行记录及日志。
- 任务重试与幂等（[ADR-009](docs/decisions/009-task-retry-and-idempotency.md)）：每次尝试新建执行记录、错误分类与退避、任务 deadline、`Idempotency-Key`、Agent 结果幂等重放。
- Agent 传输层重试增加次数上限（`retry_max_count`）与随机抖动（Python / Go 双运行时）。
- 前端引入 Vitest 单元测试与 ESLint；CI 前端作业增加 lint 与 test。
- 新增 Alembic 数据库迁移体系（`backend/migrations/`、`backend/alembic.ini`、ADR-008）；基线 `0001_initial` 在真实 Schema 上验证 `alembic check` 差异为 0。
- 新增根 `LICENSE`（Apache-2.0）。
- 新增 `backend/entrypoint.sh`：backend 容器启动先执行 `alembic upgrade head` 再启动 uvicorn。
- 新增优化路线图 `docs/optimization-plan.md`、任务重试设计 `docs/architecture/task-retry-strategy.md`。
- 新增后端代码质量门禁：`backend/pyproject.toml`（ruff / mypy / pytest / coverage 配置）、`backend/requirements-dev.txt`，CI 新增 `quality` 作业（ruff + mypy），后端测试接入覆盖率报告。
- 新增 Go 版 Agent（`agent-go/`），与 Python 版双运行时并存、协议与配置 schema 对等（[ADR-007](docs/decisions/007-go-agent-dual-runtime.md)）。
- 平台支持按 `runtime` 打包/分发 Agent：`/api/v1/agent/package`、`/api/v1/agent/install.sh` 新增 `runtime=python|go`（默认 python）。
- 前端 Agent 接入向导新增运行时选择（Python 默认 / Go），安装命令与包下载按选择生成。
- 新增 `deploy/build-agent-go.sh` 与 `.github/workflows/release-agent.yml`（交叉编译 linux/amd64、arm64 并发布 Release）。
- 前端引入 Tailwind CSS v4（`@tailwindcss/vite`）并建立样式层序与主题 token（[ADR-006](docs/decisions/006-frontend-styling-tailwind.md)）。
- 前端新增暗色主题切换（浅色/深色/跟随系统），持久化于 `localStorage`（`store/theme.js`）。
- 前端布局新增桌面折叠侧栏与小屏抽屉；顶栏新增主题切换入口。
- 新增从 Docker Hub 拉取预构建镜像的部署方式：`deploy/config.dockerhub.env.tmpl` 预设 + `deploy/docker/compose.hub.yml` 纯拉取覆盖（`IMAGE_PULL_ONLY`）。

### Changed

- Agent（Python / Go）在执行失败时上报标准化 `error_type`，服务端按分类决策重试。
- 前端创建任务时携带 `Idempotency-Key` 请求头，端到端防重复创建。
- 补充 [ADR-009](docs/decisions/009-task-retry-and-idempotency.md) 的状态语义（`TIMEOUT` / `DEAD` / `DEADLINE_EXCEEDED` / CRON × 重试）。
- ORM 模型对齐真实 Schema：补齐 `DATETIME(3)`、`TINYINT`、显式索引/唯一约束/外键名及生成列 `alert_event.is_active`，使 Alembic autogenerate 差异为 0。
- 后端接入结构化 JSON 日志（`app/core/logging.py`），自动注入 `request_id` / `user_id`。
- CI 后端作业改用 `alembic upgrade head` 建表（移除正则剥离 SQL 脚本的 bootstrap），并新增 `quality`（ruff + mypy）作业与覆盖率报告。
- CI 前端作业更名为 Lint, Test & Build，并在构建前执行 `eslint` 与 `vitest`。
- `Dockerfile.backend` 拷贝迁移文件并改由 `entrypoint.sh` 启动；compose 不再挂载 SQL 初始化目录。
- 后端 `agent_package` 服务重构为按运行时构建安装包；compose 追加 `agent-go/` 只读挂载。
- 部署流程接入 Go Agent 构建：`install.sh` 安装阶段、`publish.sh` 发布阶段调用 `build-agent-go.sh`。
- 前端样式体系：Tailwind 负责布局/间距/响应式/主题，Element Plus 负责组件；语义色改用 `var(--el-color-*)`。
- 前端仪表盘与服务器详情栅格改为响应式；`MetricChart` 改用 `ResizeObserver` 随容器自适应；各列表页补充空状态。
- `main.js` 移除重复的 Element Plus CSS 引入与图标全量注册。
- `install.sh` / `reconfigure.sh` 支持纯拉取模式：`IMAGE_PULL_ONLY=true` 时只 `pull` 不本地构建。
- Go Agent 发布改用独立 tag 命名空间 `agent-v*`（与平台镜像 `v*` 区分，避免 tag 误触发平台镜像发布）。

### Fixed

- 修复 `scan_timeouts` 使用单一任务超时批量更新所有 RUNNING 执行的问题，改为按**各自任务**的 `timeout_seconds` 判定。
- 移除脚手架残留全局样式（`#app` 1126px 限制、`prefers-color-scheme` 媒体查询等）导致的后台布局污染。

### Removed

- 移除 `deploy/mysql/init/ops_monitor_schema.sql`，Schema 单一来源转为 Alembic 迁移。

## [0.2.0] - 2026-10-02

### Added

- 部署配置源改为 KV 文件 `deploy/config.env`（Bash `source`），新增 `deploy/migrate-config.sh` 自动迁移旧 `deploy/config.yml` 并逐项保留密钥。
- 前端新增剪贴板降级工具 `frontend/src/utils/clipboard.js`。
- 后端新增查询参数工具 `backend/app/utils/params.py`（`optional_int`：空串按未传处理并保留范围校验）。
- 镜像发布：`.github/workflows/publish.yml` 在 tag `v*` 时构建并推送 Docker Hub；`deploy/publish.sh` 本地构建并推送 Harbor。
- 新增根 `VERSION` 文件作为发布版本来源。

### Changed

- 移除部署脚本的宿主机 Python/PyYAML 依赖：`prepare.py` → 纯 bash `prepare.sh`；配置模板 `config.yml.tmpl` → `config.env.tmpl`。
- nginx 镜像仓库名由 `ops-monitor-nginx` 统一为 `ops-monitor-frontend`（`prepare.sh`、`compose.yml`）。
- CI 增加手动触发、并发取消与依赖缓存，并支持被发布流程 `workflow_call` 复用。
- 部署相关文档同步为 KV 配置与无宿主 Python。
- 部署配置收敛：Docker 相关文件集中到 `deploy/docker/`（`compose.yml`、`Dockerfile.backend`）。
- SQL 初始化脚本由 `sql/` 归位到 `deploy/mysql/init/`。

### Fixed

- 修复接入向导复制在非安全上下文（HTTP 访问）下静默失效；脚本预览由居中改为左对齐。
- 修复用户管理 `status` 传空串导致的参数校验失败（`40000`）；请求层统一剔除空查询参数。
- 修复服务器管理在平台冷启动/后端重启期间显示 `502` 原始错误：Nginx 等待后端健康、`/api` 网关错误返回 JSON，前端友好提示并对 GET 自动重试。
- 修复后端种子初始化在数据库未就绪时崩溃重启（`OperationalError` 退避重试）。
- 修复 compose 迁移导致的相对挂载失效（agent/systemd/certs 挂载与数据默认路径）。

### Removed

- 移除 Agent 容器化部署（`Dockerfile.agent`）；Agent 统一以 systemd 原生部署。

## [0.1.0] - 2026-09-23

首个已交付版本。

### Added

- Backend：FastAPI 应用、统一响应与异常、JWT 认证、RBAC 鉴权、操作审计中间件。
- Agent：系统指标/服务状态采集、注册/心跳/指标/资产/服务上报、受控任务执行。
- 前端：Vue 3 管理端（登录、Dashboard、服务器管理、监控图表、告警中心、任务中心、用户管理）。
- 服务器资产管理：注册、凭证、在线状态（心跳判定）。
- 监控：指标查询（latest/history/summary）、分桶聚合与网络速率差分、Dashboard。
- 告警：阈值规则、事件状态机、确认/恢复、默认规则。
- 服务管理：服务状态监控、受控启停/重启/日志、白名单。
- 自动化任务：单机/批量/定时、执行记录与日志。
- 部署：Docker 镜像、Docker Compose 配置化部署（`deploy/config.yml` + 脚本）、Nginx 反代、HTTPS 预留。
- Agent 分发：平台托管安装包下载与一键安装命令。
- 文档：架构、模块、参考、运维文档体系与初始 ADR。

### Changed

- 文档结构由按开发阶段编号重构为按读者问题组织。

### Fixed

### Removed

- 移除旧阶段文档（内容迁移至新结构）。
