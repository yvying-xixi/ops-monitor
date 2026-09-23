# 故障排查

## Scope

覆盖平台（Backend/数据库/前端/部署）与 Agent 的常见故障排查。

## Quick Diagnosis

| 检查 | 命令 |
| --- | --- |
| 容器状态 | `docker compose -f deploy/docker/compose.yml --env-file deploy/.env ps` |
| 健康检查 | `curl http://<host>:<port>/api/v1/health` |
| 后端日志 | `docker compose -f deploy/docker/compose.yml --env-file deploy/.env logs -f backend` |
| Agent 状态 | `systemctl status server-agent --no-pager` |
| Agent 日志 | `journalctl -u server-agent -f` |

## Backend Issues

| 现象 | 排查/处理 |
| --- | --- |
| 健康检查 503 | `/health` 返回 `{db, redis}`；确认 mysql/redis 容器 healthy、密码一致 |
| 启动即退出 | 查看日志；常见为 `CORS_ORIGINS` 等环境变量解析失败或数据库不可达 |
| 接口 500 | 查看后端日志与 `sys_operation_log` 的 `error_message` |

## Database Issues

| 现象 | 排查/处理 |
| --- | --- |
| 表不存在 | 首启应执行 `sql/` 建表；确认 `data.volume_dir` 为空或已初始化 |
| 连接被拒 | 确认 mysql healthy 且 `DB_PASSWORD` 与 config 一致 |
| 数据丢失 | 确认 `data.volume_dir` 未被清空（见 [backup.md](backup.md)） |

## Frontend Issues

| 现象 | 排查/处理 |
| --- | --- |
| 页面空白/资源 404 | 前端镜像是否随代码重建（`docker compose -f deploy/docker/compose.yml --env-file deploy/.env up -d --build nginx`） |
| 接口 401 反复跳登录 | Token 失效或后端 `JWT_SECRET_KEY` 变更 |
| 刷新后菜单/权限异常 | 会话恢复依赖 `/auth/me`，确认后端可达 |

## Agent Issues

| 现象 | 排查/处理 |
| --- | --- |
| `401 服务器编码与凭证不匹配` | `server_code` 用了主机名；改为平台「编码」 |
| `401 Agent 凭证无效` | Token 错误/撤销/过期，重新生成 |
| `ModuleNotFoundError: No module named 'agent'` | 需在部署根用 `python -m agent.main` |
| 服务状态 UNKNOWN / 控制失败 | 目标机无 systemd/服务或权限不足（`systemctl is-active <svc>` 自查） |
| 状态一直 OFFLINE | 检查服务端地址可达、心跳周期、`/api/v1/health` |

## Deployment Issues

| 现象 | 排查/处理 |
| --- | --- |
| 端口被占用 | 修改 `config.yml` 的 `http.port` 或释放端口 |
| 缺少 PyYAML | `apt install -y python3-yaml` 或 `pip install pyyaml` |
| 健康检查超时 | 查看 backend 日志；确认 mysql/redis 就绪 |
| 外网无法访问 | 检查防火墙/安全组与 `hostname` 配置；公网建议 HTTPS |

## Logs and Diagnostics

- 应用日志：backend stdout（`docker compose logs`）。
- 审计日志：`sys_operation_log`、`sys_login_log`。
- 任务日志：`ops_task_log`。
- Agent 日志：`journalctl -u server-agent` 或 `log.file`。

## Common Errors

见 [reference/error-codes.md](../reference/error-codes.md)。

## Recovery Guidance

- 数据恢复见 [recovery.md](recovery.md)。
- 服务不可用时的重建见 [deployment.md](deployment.md)。

## TODO

> **TODO**: 补充故障现象—根因—处置的完整矩阵（随实际运行积累）。
