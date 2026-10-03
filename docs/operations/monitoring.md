# 平台可观测性

> 本文描述 ops-monitor 平台自身的可观测性，不负责说明被监控服务器的业务指标（后者见 [modules/monitoring.md](../modules/monitoring.md)）。

## 健康检查

`GET /api/v1/health`：检查数据库与 Redis 连通性，返回：

```json
{ "code": 0, "message": "ok", "data": { "db": true, "redis": true } }
```

任一组件不可用返回 HTTP 503。

## 容器健康

- Compose 为 mysql/redis/backend/nginx 配置 healthcheck；`docker compose -f deploy/docker/compose.yml --env-file deploy/.env ps` 显示 healthy。
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

## 指标生命周期与归档

- 原始指标（`monitor_server_metric` 等）：保留 `METRIC_RETENTION_DAYS`（默认 7 天）。
- 每日归档任务：先把超期原始指标按 `(server, 日期)` 聚合写入 `monitor_server_metric_daily`（AVG/MAX/样本数，幂等 upsert），再删除超期原始指标；聚合保留 `METRIC_AGG_RETENTION_DAYS`（默认 180 天）。
- 说明：原始指标表含外键，**不做 MySQL 分区**；以「聚合归档 + 保留清理」实现数据生命周期。

## Prometheus 指标

`GET /metrics`（backend 根路径，非 `/api`，默认仅内网可达）暴露平台自有指标：

| 指标 | 类型 | 说明 |
| --- | --- | --- |
| `ops_agent_status{status}` | Gauge | 按 Agent 状态统计的服务器数（ONLINE/WARNING/OFFLINE/UNKNOWN） |
| `ops_server_total` | Gauge | 启用中的服务器总数 |
| `ops_alert_active{severity}` | Gauge | 按严重级别统计的活动告警数 |
| `ops_task_status{status}` | Gauge | 按状态统计的任务数 |

- 指标在抓取时从数据库汇总，多 worker 部署下保持一致；高基数标识（server_id/task_id 等）不作为标签。
- 访问控制：`METRICS_ENABLED=false` 关闭（返回 404）；`METRICS_TOKEN` 非空时需 `Authorization: Bearer <token>`。
- backend 端口不对外暴露，Prometheus 需与平台同网络抓取 `backend:8000/metrics`。

Prometheus 抓取示例：

```yaml
scrape_configs:
  - job_name: ops-monitor
    metrics_path: /metrics
    authorization:
      credentials: "<METRICS_TOKEN>"
    static_configs:
      - targets: ["backend:8000"]
```

## OpenTelemetry 链路追踪

默认关闭；`OTEL_ENABLED=true` 时对以下组件自动埋点：

- FastAPI 请求（排除 `/metrics`、`/api/v1/health`）
- SQLAlchemy 数据库调用（使用应用 engine）
- Redis 调用

- 配置 `OTEL_EXPORTER_OTLP_ENDPOINT`（OTLP/HTTP，如 `http://otel-collector:4318/v1/traces`）后经 `BatchSpanProcessor` 导出；为空时仅生成 span。
- `trace_id` 自动注入结构化日志（`app/core/logging.py`），可与日志关联。
- 后端链路覆盖：前端 → Nginx → FastAPI → MySQL/Redis → Task 派发；Agent 侧归因通过请求头透传 `trace_id`（后续项）。

## 系统资源

> **待办**: 补充平台容器自身的资源监控方式（cgroup/宿主监控）。

## 接口延迟与错误率

> **待办**: 补充基于中间件的 HTTP 延迟/错误率指标（可随 OpenTelemetry 一并接入）。

## 待办

> **待办**: 补充告警自监控（平台自身异常时的通知路径）。
> **待办**: 补充备份/恢复演练的可观测性指标。
