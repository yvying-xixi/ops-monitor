# 性能与容量

> 本文描述如何对 Ops Monitor 进行性能压测、记录基线与定位瓶颈。

## 工具

- 主工具：[Locust](https://locust.io/)（`benchmarks/locustfile.py`，见 [benchmarks/README.md](../../benchmarks/README.md)）。
- 可选：`benchmarks/smoke.py`（标准库实现的只读 smoke，用于快速自检与无 Locust 环境）。

## 压测场景

- 只读混合：Dashboard、服务器列表/详情、指标 latest/history/summary、告警列表/规则、任务列表。
- 写场景（可选）：创建 `SERVICE_CHECK` 任务。

## 运行

```bash
pip install -r benchmarks/requirements.txt
BASE_URL=http://127.0.0.1:8000 USERS=50 SPAWN_RATE=5 RUN_TIME=60s ./benchmarks/run.sh

# 轻量 smoke
BASE_URL=http://127.0.0.1:8000 USERS=20 DURATION=15 python benchmarks/smoke.py
```

## 记录基线

将结果归档到 `benchmarks/reports/`（模板见 benchmarks/README.md）。基线应记录：

- 平台版本 / commit、部署形态（单实例/多副本、资源限制）
- 数据规模（服务器数、指标行数、任务数）
- 压测参数与结果（RPS、P50/P95/P99、失败率）
- 结论与瓶颈

## 关注指标

- API QPS、P50/P95/P99、错误率。
- 数据库 QPS / 慢查询、Redis QPS。
- 指标写入吞吐、任务吞吐、告警评估延迟。

## 注意

- 仅在独立测试环境执行；写场景会产生数据。
- 压测前确认调度/重试等后台作业的影响，必要时临时调低频率。
- 服务自身指标见 [monitoring.md](monitoring.md)（Prometheus `/metrics`）。
