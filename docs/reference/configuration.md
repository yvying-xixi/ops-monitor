# 配置参考

> 本文档描述后端、部署与 Agent 的配置项。可复制模板：`backend/app/core/.env.example`（后端本地开发）、`deploy/config.env.tmpl`（平台部署）、`agent/config/config.yaml.example`（Agent）。

## 平台部署（`deploy/config.env`）

配置源为 `deploy/config.env`（由 `config.env.tmpl` 生成），经 `prepare.sh` 渲染为 `deploy/.env` 供 Compose 使用。

`config.env` 是 Bash-compatible 配置文件（由 shell `source` 执行），**仅允许受信任的部署管理员编辑**。

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `HOSTNAME` | 127.0.0.1 | 平台对外地址（CORS 与访问提示） |
| `HTTP_PORT` | 80 | 对外 HTTP 端口 |
| `HTTPS_ENABLED` | false | 启用 HTTPS |
| `HTTPS_PORT` | 443 | HTTPS 端口 |
| `HTTPS_CERTIFICATE` / `HTTPS_PRIVATE_KEY` | — | 证书/私钥路径 |
| `DB_NAME` | ops_monitor | 业务库名 |
| `DB_PASSWORD` | 自动生成 | MySQL 密码 |
| `REDIS_PASSWORD` | 自动生成 | Redis 密码 |
| `JWT_SECRET_KEY` | 自动生成 | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | 120 | Token 有效期（分钟） |
| `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` | admin / 自动生成 | 初始管理员（仅首次 seed） |
| `SEED_INIT_DATA` | true | 启动时是否初始化种子数据 |
| `METRIC_RETENTION_DAYS` | 7 | 原始指标保留天数 |
| `METRIC_AGG_RETENTION_DAYS` | 180 | 指标日聚合归档保留天数 |
| `TASK_RETENTION_DAYS` | 30 | 任务执行记录保留天数 |
| `OPERATION_LOG_ENABLED` | true | 操作审计开关 |
| `METRICS_ENABLED` | true | Prometheus `/metrics` 开关 |
| `METRICS_TOKEN` | 空 | `/metrics` 访问令牌（空则不鉴权，仅内网可达） |
| `AGENT_REQUIRE_SIGNATURE` | false | 是否强制 Agent 请求签名 |
| `AGENT_SIGNATURE_MAX_SKEW` | 300 | Agent 请求时间戳允许偏差（秒） |
| `SCHEDULER_LOCK_ENABLED` | true | 调度作业 Redis 分布式锁开关 |
| `SCHEDULER_LOCK_TTL_SECONDS` | 600 | 调度锁 TTL（秒） |
| `DISCOVERY_ENABLED` | false | 只读服务器发现开关 |
| `DISCOVERY_ALLOWED_CIDRS` | `[]` | 允许扫描的 CIDR 白名单（JSON 列表） |
| `BACKUP_DIR` | ./backups | 备份归档目录（相对 `deploy/` 或绝对路径） |
| `BACKUP_RETENTION_DAYS` | 14 | 备份保留天数 |
| `BACKUP_INCLUDE_CONFIG` | true | 备份是否包含 `config.env` |
| `BACKUP_INCLUDE_REDIS` | false | 备份是否包含 Redis 快照 |
| `BACKUP_INCLUDE_NGINX` | false | 备份是否包含 nginx 配置与证书 |
| `BACKUP_POST_CMD` | 空 | 备份后钩子（可读取 `$ARCHIVE`） |
| `IMAGE_REGISTRY` | 空 | 镜像 registry（空则本地构建；Docker Hub 用 `docker.io/<namespace>`） |
| `IMAGE_TAG` | latest | 镜像标签 |
| `IMAGE_PULL_ONLY` | false | true 时纯拉取（加载 `compose.hub.yml`，不本地构建） |
| `DATA_VOLUME_DIR` | ./data | 数据持久化目录（宿主，相对 `deploy/`） |

> 以下键由 `prepare.sh` 派生写入 `deploy/.env`，不在 `config.env` 中：`CORS_ORIGINS`、`BACKEND_IMAGE`、`NGINX_IMAGE`。

## 后端环境变量

后端通过环境变量读取（Compose 注入；本地开发用 `backend/app/core/.env`）。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DB_HOST` | 127.0.0.1 | MySQL 地址 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_USER` | root | MySQL 用户 |
| `DB_PASSWORD` | 空 | MySQL 密码 |
| `DB_NAME` | ops_monitor | 数据库名 |
| `REDIS_URL` | redis://127.0.0.1:6379/0 | Redis 连接串 |
| `JWT_SECRET_KEY` | change-me | JWT 签名密钥（**上线必改**） |
| `JWT_ALGORITHM` | HS256 | JWT 算法 |
| `JWT_EXPIRE_MINUTES` | 120 | Token 有效期（分钟） |
| `CORS_ORIGINS` | ["*"] | 允许的跨域来源（JSON 列表） |
| `SEED_INIT_DATA` | true | 是否初始化种子数据 |
| `SEED_ADMIN_USERNAME` | admin | 初始管理员账号 |
| `SEED_ADMIN_PASSWORD` | admin123456 | 初始管理员密码（**上线必改**） |
| `OPERATION_LOG_ENABLED` | true | 操作审计中间件开关 |
| `AGENT_STATUS_REFRESH_SECONDS` | 30 | Agent 状态刷新周期 |
| `ALERT_EVALUATE_INTERVAL_SECONDS` | 10 | 告警评估周期 |
| `METRIC_RETENTION_DAYS` | 7 | 原始指标保留天数（超期先聚合归档再删除） |
| `METRIC_AGG_RETENTION_DAYS` | 180 | 指标日聚合归档保留天数 |
| `METRIC_CLEANUP_ENABLED` | true | 指标归档/清理开关 |
| `TASK_RETENTION_DAYS` | 30 | 终态任务执行记录保留天数 |
| `TASK_CLEANUP_ENABLED` | true | 任务执行清理开关 |
| `LOG_LEVEL` | INFO | 日志级别（结构化 JSON） |
| `METRICS_ENABLED` | true | Prometheus `/metrics` 开关 |
| `METRICS_TOKEN` | 空 | `/metrics` 访问令牌（空则不鉴权） |
| `OTEL_ENABLED` | false | OpenTelemetry 链路追踪开关 |
| `OTEL_SERVICE_NAME` | ops-monitor-backend | 上报到追踪后端的服务名 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 空 | OTLP/HTTP traces 端点（空则仅生成 span 不导出） |
| `AGENT_REQUIRE_SIGNATURE` | false | 是否强制 Agent 请求签名（Ed25519） |
| `AGENT_SIGNATURE_MAX_SKEW` | 300 | Agent 请求时间戳允许偏差（秒） |
| `SCHEDULER_LOCK_ENABLED` | true | 调度作业 Redis 分布式锁（多 worker/多实例每轮只执行一次） |
| `SCHEDULER_LOCK_TTL_SECONDS` | 600 | 调度锁 TTL（进程崩溃兜底，应大于最长作业耗时） |
| `DISCOVERY_ENABLED` | false | 只读服务器发现开关 |
| `DISCOVERY_ALLOWED_CIDRS` | `[]` | 允许扫描的 CIDR 白名单（JSON 列表，防止越权扫描） |
| `DISCOVERY_MAX_HOSTS` | 256 | 单次扫描主机数上限 |
| `DISCOVERY_SSH_PORT` | 22 | 默认探测端口 |
| `DISCOVERY_TIMEOUT_SECONDS` | 0.5 | 单主机探测超时（秒） |
| `DISCOVERY_CONCURRENCY` | 32 | 探测并发数 |
| `AGENT_BUNDLE_DIR` | 空 | Agent 安装包来源目录（容器内挂载；空则自动定位仓库根） |

## Agent 配置（Python 与 Go 通用）

Python 与 Go 两个 Agent 使用**同一份配置 schema**，可复用平台向导生成的 `config.yaml`。

| 段 | 键 | 默认 | 说明 |
| --- | --- | --- | --- |
| `server` | `url` | — | 服务端地址 |
| `server` | `token` | — | Agent 注册凭证 |
| `server` | `server_code` | — | 服务器编码（与平台一致） |
| `server` | `signing_key_file` | agent_ed25519.key | Ed25519 私钥路径（相对 config.yaml 或绝对路径；自动生成） |
| `collect` | `heartbeat_interval` | 30 | 心跳周期（秒） |
| `collect` | `metrics_interval` | 10 | 指标采集周期（秒） |
| `collect` | `assets_interval` | 60 | 资产/服务同步周期（秒） |
| `collect` | `task_poll_interval` | 5 | 任务轮询周期（秒） |
| `collect` | `retry_max_seconds` | 60 | 退避重试封顶（秒） |
| `collect` | `retry_max_count` | 2 | 单次请求传输层最大重试次数 |
| `collect` | `connect_timeout` | 5 | 连接超时（秒） |
| `collect` | `request_timeout` | 10 | 请求超时（秒） |
| `collect` | `services` | nginx,docker,ssh | 监控与受控服务白名单 |
| `log` | `level` / `file` | INFO / 空 | 日志级别与文件 |

> Go Agent 的日志级别同义映射：`DEBUG/INFO/WARN/ERROR`（`WARNING` 亦识别为 `WARN`）。

## 相关文档

- [operations/deployment.md](../operations/deployment.md)
- [operations/agent-deployment.md](../operations/agent-deployment.md)
- [decisions/004-configuration-driven-deployment.md](../decisions/004-configuration-driven-deployment.md)
