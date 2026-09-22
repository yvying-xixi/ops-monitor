# 服务器管理

> 本文描述服务器资产的管理与 Agent 接入。

## 资产字段

`ops_server` 记录主机名、IP、SSH 端口、操作系统、内核、架构、CPU 型号/核心数、内存/磁盘总量、Agent 版本、Agent 状态、最后心跳、注册时间等。

唯一约束：`server_code` 唯一；`(ip_address, ssh_port)` 唯一。

## Agent 状态

按 `last_heartbeat_at` 与当前 UTC 时间差判定：

| 最后心跳时间 | 状态 |
| --- | --- |
| ≤ 30 秒 | ONLINE |
| 30 < 心跳 ≤ 90 秒 | WARNING |
| > 90 秒 | OFFLINE |

由调度器周期刷新（默认 30s）。

## 服务器管理 API

| Method | Endpoint | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/servers` | 服务器分页列表（可按 agent_status 筛选） | admin |
| POST | `/api/v1/servers` | 创建服务器 | admin |
| GET | `/api/v1/servers/{id}` | 服务器详情 | admin |
| POST | `/api/v1/servers/{id}/agent-token` | 生成 Agent 注册凭证（明文一次） | admin |
| GET | `/api/v1/servers/{id}/services` | 服务资产与状态 | 登录 |
| PUT | `/api/v1/servers/{id}/services/{sid}/whitelist` | 服务操作白名单 | admin |

## 接入向导

前端「服务器管理 → 接入」提供向导：复制 `server_code`/`Token`、编辑服务端地址与服务白名单、生成/下载 `config.yaml`、下载 Agent 包、复制一键安装命令。

> `server_code` 是 Agent 注册匹配键，须与平台「编码」一致（非主机名）。

## 相关文档

- [operations/agent-deployment.md](../operations/agent-deployment.md)
- [reference/agent-protocol.md](../reference/agent-protocol.md)
