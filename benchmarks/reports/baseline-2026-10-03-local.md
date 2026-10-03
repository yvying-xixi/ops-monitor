# 基线 2026-10-03（本地开发环境）

> 由 `benchmarks/smoke.py` 生成，用于建立初始性能基线。非生产数据，仅供趋势参考。

## 环境

- 平台版本 / commit：`0.3.0` / `05206cf`（含本机未提交的压测脚本改动）
- 部署形态：单实例，`uvicorn --workers 1`；MySQL 8.0 与 Redis 7 为本地 Docker 容器
- 数据规模：3 台服务器；指标/任务数据近乎为空（指标接口为空查询）
- 压测参数：`USERS=20`，`DURATION=15s`，只读混合场景
- 运行：`benchmarks/smoke.py`（标准库客户端，非 Locust）

## 结果

| 接口 | 请求数 | P50(ms) | P95(ms) | P99(ms) | 失败 |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/alerts/rules` | 280 | 126.0 | 148.4 | 246.7 | 0 |
| `/api/v1/alerts?page=1&page_size=20` | 283 | 130.4 | 165.5 | 256.9 | 0 |
| `/api/v1/dashboard/overview` | 293 | 158.7 | 265.5 | 308.2 | 0 |
| `/api/v1/monitor/3/metrics/latest` | 279 | 57.5 | 74.4 | 100.3 | 0 |
| `/api/v1/monitor/3/metrics/summary?range=1h` | 276 | 55.3 | 73.6 | 78.7 | 0 |
| `/api/v1/servers/3` | 280 | 168.3 | 201.8 | 296.4 | 0 |
| `/api/v1/servers?page=1&page_size=20` | 288 | 177.6 | 281.7 | 304.2 | 0 |
| `/api/v1/tasks?page=1&page_size=20` | 280 | 158.4 | 182.8 | 268.8 | 0 |

**总体**：请求 2259，RPS 150.6，P50 139.7ms，P95 209.5ms，P99 293.0ms，失败 0。

## 观察与说明

- 单 worker + 本地容器，绝对数值偏低；多副本（nginx 轮询）应显著提升吞吐。
- 列表/详情类接口延迟较高（P95 200-280ms），主要来自单进程 + JSON 结构化日志 + 容器化 DB 网络往返。
- 指标接口（latest/summary）在此数据量下最快；需在**真实指标规模**下复测以评估聚合查询。
- 后续对比请固定相同参数与数据规模；正式基线与瓶颈定位建议使用 Locust（`benchmarks/locustfile.py`）。
