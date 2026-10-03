# 故障排查

## 范围

覆盖平台（Backend/数据库/前端/部署）与 Agent 的常见故障排查。

## 快速诊断

| 检查 | 命令 |
| --- | --- |
| 容器状态 | `docker compose -f deploy/docker/compose.yml --env-file deploy/.env ps` |
| 健康检查 | `curl http://<host>:<port>/api/v1/health` |
| 后端日志 | `docker compose -f deploy/docker/compose.yml --env-file deploy/.env logs -f backend` |
| Agent 状态 | `systemctl status server-agent --no-pager` |
| Agent 日志 | `journalctl -u server-agent -f` |

## 后端问题

| 现象 | 排查/处理 |
| --- | --- |
| 健康检查 503 | `/health` 返回 `{db, redis}`；确认 mysql/redis 容器 healthy、密码一致 |
| 启动即退出 | 查看日志；常见为 `CORS_ORIGINS` 等环境变量解析失败或数据库不可达 |
| 接口 502/503（冷启动） | 后端尚未就绪时 Nginx 返回 `50300`（服务暂未就绪）；等待 backend healthy，或 `docker compose logs backend` 确认是否崩溃重启（种子初始化已带 DB 退避重试） |
| 接口 500 | 查看后端日志与 `sys_operation_log` 的 `error_message` |

## 数据库问题

| 现象 | 排查/处理 |
| --- | --- |
| 表不存在 | backend 容器启动时应执行 `alembic upgrade head`；查看 backend 日志与迁移版本（`alembic current`） |
| 连接被拒 | 确认 mysql healthy 且 `DB_PASSWORD` 与 config 一致 |
| 数据丢失 | 确认 `DATA_VOLUME_DIR` 未被清空（见 [backup.md](backup.md)） |

## 前端问题

| 现象 | 排查/处理 |
| --- | --- |
| 页面空白/资源 404 | 前端镜像是否随代码重建（`docker compose -f deploy/docker/compose.yml --env-file deploy/.env up -d --build nginx`） |
| 接口 401 反复跳登录 | Token 失效或后端 `JWT_SECRET_KEY` 变更 |
| 刷新后菜单/权限异常 | 会话恢复依赖 `/auth/me`，确认后端可达 |
| 接入向导“复制”无反应 | 非 HTTPS/`localhost` 访问时浏览器禁用 Clipboard API，现已自动降级 `execCommand`；仍失败可手动选择文本复制 |
| 用户管理报 `query.status ... integer` | 清空过滤不应发送空 `status`；确认前端为最新构建（请求层会剔除空查询参数） |

## Agent 问题

| 现象 | 排查/处理 |
| --- | --- |
| `401 服务器编码与凭证不匹配` | `server_code` 用了主机名；改为平台「编码」 |
| `401 Agent 凭证无效` | Token 错误/撤销/过期，重新生成 |
| `ModuleNotFoundError: No module named 'agent'`（Python 版） | 需在部署根用 `python -m agent.main` |
| Go 版安装报「未找到匹配的二进制」 | 包内 `dist/` 缺少对应架构产物；运行 `./deploy/build-agent-go.sh` 或从 Release 获取 |
| Go 版启动即退出并提示 `加载配置失败` | 检查 `--config` 路径及 `server.url/token/server_code` 是否填写 |
| Go 二进制报 `Exec format error` | 架构不匹配；确认目标机 `uname -m` 与安装包内二进制一致（amd64/arm64） |
| 服务状态 UNKNOWN / 控制失败 | 目标机无 systemd/服务或权限不足（`systemctl is-active <svc>` 自查） |
| 状态一直 OFFLINE | 检查服务端地址可达、心跳周期、`/api/v1/health` |

## 部署问题

| 现象 | 排查/处理 |
| --- | --- |
| 端口被占用 | 修改 `config.env` 的 `HTTP_PORT` 或释放端口 |
| 缺少 `config.env` | 有旧 `config.yml` 时运行 `./deploy/install.sh` 自动迁移；否则从 `config.env.tmpl` 生成 |
| 健康检查超时 | 查看 backend 日志；确认 mysql/redis 就绪 |
| 外网无法访问 | 检查防火墙/安全组与 `HOSTNAME` 配置；公网建议 HTTPS |

## 日志与诊断

- 应用日志：backend stdout（`docker compose logs`）。
- 审计日志：`sys_operation_log`、`sys_login_log`。
- 任务日志：`ops_task_log`。
- Agent 日志：`journalctl -u server-agent` 或 `log.file`。

## 常见错误

见 [reference/error-codes.md](../reference/error-codes.md)。

## 恢复指引

- 数据恢复见 [recovery.md](recovery.md)。
- 服务不可用时的重建见 [deployment.md](deployment.md)。

## 待办

> **待办**: 补充故障现象—根因—处置的完整矩阵（随实际运行积累）。
