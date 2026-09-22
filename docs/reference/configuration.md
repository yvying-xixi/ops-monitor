# 配置 Reference

> 本文档描述后端、部署与 Agent 的配置项。`.env.example` / `config.yml.tmpl` 是可复制模板，本文件是完整说明。

## 平台部署（`deploy/config.yml`）

配置源为 `deploy/config.yml`（由 `config.yml.tmpl` 生成），经 `prepare.py` 渲染为 `deploy/.env` 供 Compose 使用。

| 段 | 键 | 默认 | 说明 |
| --- | --- | --- | --- |
| — | `hostname` | 127.0.0.1 | 平台对外地址（CORS 与访问提示） |
| `http` | `port` | 80 | 对外 HTTP 端口 |
| `https` | `enabled` | false | 启用 HTTPS |
| `https` | `port` | 443 | HTTPS 端口 |
| `https` | `certificate` / `private_key` | — | 证书/私钥路径 |
| `database` | `name` | ops_monitor | 业务库名 |
| `database` | `password` | 自动生成 | MySQL 密码 |
| `redis` | `password` | 自动生成 | Redis 密码 |
| `jwt` | `secret_key` | 自动生成 | JWT 签名密钥 |
| `jwt` | `expire_minutes` | 120 | Token 有效期（分钟） |
| `admin` | `username` / `password` | admin / 自动生成 | 初始管理员（仅首次 seed） |
| `seed` | `init` | true | 启动时是否初始化种子数据 |
| `metrics` | `retention_days` | 7 | 指标保留天数 |
| `operation_log` | `enabled` | true | 操作审计开关 |
| `image` | `registry` | 空 | 镜像 registry（空则本地构建） |
| `image` | `tag` | latest | 镜像标签 |
| `data` | `volume_dir` | ./data | 数据持久化目录（宿主，相对 `deploy/`） |

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
| `METRIC_RETENTION_DAYS` | 7 | 指标保留天数 |
| `METRIC_CLEANUP_ENABLED` | true | 指标清理开关 |
| `AGENT_BUNDLE_DIR` | 空 | Agent 安装包来源目录（容器内挂载；空则自动定位仓库根） |

## Agent 配置（`agent/config/config.yaml`）

| 段 | 键 | 默认 | 说明 |
| --- | --- | --- | --- |
| `server` | `url` | — | 服务端地址 |
| `server` | `token` | — | Agent 注册凭证 |
| `server` | `server_code` | — | 服务器编码（与平台一致） |
| `collect` | `heartbeat_interval` | 30 | 心跳周期（秒） |
| `collect` | `metrics_interval` | 10 | 指标采集周期（秒） |
| `collect` | `assets_interval` | 60 | 资产/服务同步周期（秒） |
| `collect` | `task_poll_interval` | 5 | 任务轮询周期（秒） |
| `collect` | `retry_max_seconds` | 60 | 退避重试封顶（秒） |
| `collect` | `connect_timeout` | 5 | 连接超时（秒） |
| `collect` | `request_timeout` | 10 | 请求超时（秒） |
| `collect` | `services` | nginx,docker,ssh | 监控与受控服务白名单 |
| `log` | `level` / `file` | INFO / 空 | 日志级别与文件 |

## 相关文档

- [operations/deployment.md](../operations/deployment.md)
- [operations/agent-deployment.md](../operations/agent-deployment.md)
- [decisions/004-configuration-driven-deployment.md](../decisions/004-configuration-driven-deployment.md)
