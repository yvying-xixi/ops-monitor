# Agent Protocol

> 本文描述 Agent 与 Backend 之间的通信协议。实现见 `agent/` 与 `backend/app/api/v1/agent.py`。

## Overview

通信方向恒为 **Agent → Backend**（主动上报/轮询），后端不主动连接 Agent。所有 Agent 接口位于 `/api/v1/agent/*`，使用独立 Token 鉴权。

## Authentication

- 请求头：`Authorization: Bearer <Agent Token>`。
- Token 由平台生成，数据库仅存 SHA-256 哈希；`register` 时 Token 在请求体与请求头中同时携带。
- 校验失败返回 `401`（错误码 `40103`）。

## Registration

`POST /api/v1/agent/register`

```json
{
  "server_code": "web-01",
  "token": "<TOKEN>",
  "hostname": "web-01",
  "os_name": "Ubuntu",
  "os_version": "22.04",
  "kernel_version": "5.15.0",
  "architecture": "x86_64",
  "cpu_model": "Intel Xeon",
  "cpu_cores": 4,
  "memory_total_bytes": 8589934592,
  "disk_total_bytes": 107374182400,
  "agent_version": "1.0.0"
}
```

服务端校验 Token 与 `server_code` 匹配后回写系统信息并置 `ONLINE`，返回 `{server_id, agent_status}`。

## Heartbeat

`POST /api/v1/agent/heartbeat`

```json
{ "server_id": 10001, "agent_version": "1.0.0", "timestamp": "2026-09-23T00:00:00+00:00" }
```

服务端更新 `last_heartbeat_at` 并记录 `ops_agent_heartbeat`。

## Metrics

`POST /api/v1/agent/metrics`

```json
{
  "server_id": 10001,
  "timestamp": "2026-09-23T00:00:00+00:00",
  "cpu_usage": 72.3,
  "memory_usage": 61.2,
  "memory_used_bytes": 123456789,
  "disk_usage": 81.4,
  "network_in_bytes": 1000000,
  "network_out_bytes": 2000000,
  "load_1m": 2.31, "load_5m": 1.8, "load_15m": 1.2,
  "tcp_connections": 126,
  "uptime_seconds": 360000
}
```

时间合法性校验：与服务器时间偏差超过 300s 拒绝（错误码 `40001`）。

## Assets

`POST /api/v1/agent/assets`：同步磁盘与网卡资产（幂等 upsert，缺失项删除）。

## Services

`POST /api/v1/agent/services`：上报服务状态 `[{service_name, current_status}]`。

## Task Polling

`GET /api/v1/agent/tasks/pending`：领取本服务器待执行任务，服务端将执行置 RUNNING，返回：

```json
[{ "execution_id": 1, "task_id": 10, "action": "STATUS", "service_name": "nginx", "timeout_seconds": 60 }]
```

## Task Result

`POST /api/v1/agent/task/result`

```json
{ "execution_id": 1, "status": "SUCCESS", "exit_code": 0, "result_text": "active", "error_message": null, "logs": "..." }
```

服务端更新执行状态、写 `ops_task_log`，并聚合任务状态。

## Package and Installer

- `GET /api/v1/agent/package`：下载 Agent 安装包（tar.gz，公开）。
- `GET /api/v1/agent/install.sh`：获取一键安装脚本（公开）。

## Retry Policy

网络失败采用指数退避重试（1s/2s/4s…，封顶 `retry_max_seconds`）。详见 `agent/reporter/client.py`。

## Timeout Policy

- HTTP 请求超时：`request_timeout`（默认 10s）。
- 任务执行超时：由任务 `timeout_seconds` 决定；Agent executor 亦设置超时。

## Idempotency

- 资产/服务同步为幂等 upsert。
- 任务结果重复回传被拒绝（执行已结束返回 `400`）。

## Error Handling

统一响应 `{code, message, data}`；错误码见 [error-codes.md](error-codes.md)。

## Compatibility

> **TODO**: 补充协议版本号与向后兼容策略（当前无显式协议版本字段）。
