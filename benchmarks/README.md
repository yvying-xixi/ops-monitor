# 性能压测（Benchmarks）

> 基于 [Locust](https://locust.io/) 的 Ops Monitor API 负载测试，用于建立性能基线并定位瓶颈。

## 场景

只读热点接口（默认）：

- `GET /api/v1/dashboard/overview`
- `GET /api/v1/servers`、`GET /api/v1/servers/{id}`
- `GET /api/v1/monitor/{id}/metrics/latest|history|summary`
- `GET /api/v1/alerts`、`GET /api/v1/alerts/rules`
- `GET /api/v1/tasks`

可选写场景（`OPS_ENABLE_WRITE=1`）：`POST /api/v1/tasks`（SERVICE_CHECK，只读检查）。

## 准备

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r benchmarks/requirements.txt
```

被测平台需可访问，并准备好一个管理员账号与至少一台服务器（用于指标类接口）。

## 运行

```bash
BASE_URL=http://127.0.0.1:8000 USERS=50 SPAWN_RATE=5 RUN_TIME=60s ./benchmarks/run.sh

# 启用写场景
OPS_ENABLE_WRITE=1 BASE_URL=... ./benchmarks/run.sh

# 指定账号/服务器
OPS_USERNAME=admin OPS_PASSWORD=*** OPS_SERVER_ID=1 ./benchmarks/run.sh
```

也可用 Web UI（去掉 `--headless` 与 `-u/-r/-t`）：

```bash
locust -f benchmarks/locustfile.py -H http://127.0.0.1:8000
```

## 记录基线

把 Locust 汇总（Requests/s、P50/P95/P99、失败率）整理到 `benchmarks/reports/`，参考模板：

```markdown
# 基线 YYYY-MM-DD

- 平台版本 / commit：
- 部署形态（单实例 / 多副本、CPU/内存限制）：
- 数据规模（服务器数 / 指标行数 / 任务数）：
- 压测参数（users / spawn / duration）：

| 场景 | RPS | P50 | P95 | P99 | 失败率 |
| --- | --- | --- | --- | --- | --- |
| 只读混合 | | | | | |

结论与瓶颈：
```

## 注意

- 压测会写入任务（写场景）并产生审计/指标数据，请使用**独立测试环境**。
- Agent 上报/签名接口未纳入默认场景（需 Agent Token 与私钥）；如需测试请单独扩展。
- 不要在生产环境执行写场景。
