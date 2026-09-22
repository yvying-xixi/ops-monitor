# 平台可观测性

> 本文描述 ops-monitor 平台自身的可观测性，不负责说明被监控服务器的业务指标（后者见 [modules/monitoring.md](../modules/monitoring.md)）。

## 健康检查

`GET /api/v1/health`：检查数据库与 Redis 连通性，返回：

```json
{ "code": 0, "message": "ok", "data": { "db": true, "redis": true } }
```

任一组件不可用返回 HTTP 503。

## 容器健康

- Compose 为 mysql/redis/backend/nginx 配置 healthcheck；`docker compose ps` 显示 healthy。
- backend 镜像内置 HEALTHCHECK（`/api/v1/health`）。

## 平台日志

- Backend 应用日志：API 请求、异常、数据库错误、启动/关闭。
- 审计日志：`sys_operation_log`、`sys_login_log`。
- 任务日志：`ops_task_log`。

## Agent 在线率

- 通过 `ops_server.agent_status` 统计（ONLINE/WARNING/OFFLINE）。
- Dashboard `server_stats` 展示；调度器周期刷新。

## 任务积压

- 通过 `ops_task_execution.status` 观察 PENDING/RUNNING 数量。
- 超时扫描（30s）将长时间 RUNNING 置 TIMEOUT。

## 系统资源

> **TODO**: 补充平台容器自身的资源监控方式（cgroup/宿主监控）。

## API 延迟与错误率

> **TODO**: 补充基于日志或指标中间件的延迟/错误率统计方案。

## TODO

> **TODO**: 补充告警自监控（平台自身异常时的通知路径）。
> **TODO**: 补充备份/恢复演练的可观测性指标。
