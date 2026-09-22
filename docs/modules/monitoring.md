# 监控中心

> 本文描述 ops-monitor 对服务器和服务进行监控的功能，不负责说明平台自身的健康检查和运行状态（后者见 [operations/monitoring.md](../operations/monitoring.md)）。

## 监控范围

CPU、内存、磁盘、网络、Load、TCP 连接数、系统运行时间、进程、服务状态。采集由 Agent 完成（详见 [architecture/agent.md](../architecture/agent.md)）。

## 监控数据

- 指标落 `monitor_server_metric`；磁盘/网卡/容器/进程有独立表。
- 网络为**累计字节数**，展示时按时间桶差分输出速率（MB/s）。

## 监控 API

| Method | Endpoint | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/servers/{id}/metrics/latest` | 最近一条指标 | 登录 |
| GET | `/api/v1/servers/{id}/metrics/history` | 原始历史（分页） | 登录 |
| GET | `/api/v1/servers/{id}/metrics/summary?range=1h\|6h\|24h\|7d` | 分桶聚合（avg/max/min + 网络速率） | 登录 |
| GET | `/api/v1/servers/{id}/assets` | 磁盘/网卡资产 | 登录 |
| GET | `/api/v1/dashboard/overview` | 状态统计 + 平均使用率 + 服务器列表 | 登录 |

## 聚合与差分

时间桶（summary）：

| range | 时长 | 桶宽 | 点数上限 |
| --- | --- | --- | --- |
| 1h | 3600s | 60s | 60 |
| 6h | 21600s | 60s | 360 |
| 24h | 86400s | 300s | 288 |
| 7d | 604800s | 3600s | 168 |

- 数值指标：SQL 按 `FLOOR(UNIX_TIMESTAMP/N)*N` 分桶 + `AVG/MAX/MIN`。
- 网络：桶内取 MAX 采样，服务层对相邻桶差分得速率。

## Dashboard

- 统计卡片：服务器总数/在线/警告/离线、CPU/内存/磁盘平均使用率、实时告警。
- 服务器列表含最新指标摘要，10s 自动刷新。
- 平均使用率基于每台服务器最新指标，无指标服务器不计入。

## 数据生命周期

- 指标保留期 `METRIC_RETENTION_DAYS`（默认 7 天），调度器每日清理（`METRIC_CLEANUP_ENABLED` 控制）。

## 相关文档

- [architecture/frontend.md](../architecture/frontend.md)
- [reference/database.md](../reference/database.md)
