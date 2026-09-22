# ADR-002: Agent 采用主动上报模型

## Status

Accepted

## Context

被监控服务器可能位于 NAT 或防火墙环境中，Backend 无法稳定地主动访问 Agent。需要选择 Agent 与 Backend 的通信模型，并处理离线与重试。

## Decision

Agent **主动**向 Backend 上报与轮询：

- Heartbeat（`POST /agent/heartbeat`）
- Metrics / Assets / Services（`POST /agent/metrics|assets|services`）
- Task 领取与结果（`GET /agent/tasks/pending`、`POST /agent/task/result`）

网络失败采用指数退避重试；进程异常由 systemd `Restart=always` 拉起。

## Alternatives

### Backend 主动轮询

- 优点：Backend 统一控制采集周期；Agent 实现简单。
- 缺点：对 NAT/防火墙不友好；Backend 需维护大量连接与超时。

### WebSocket

- 优点：双向、实时性好。
- 缺点：连接维护与重连复杂；网络环境要求高。

## Consequences

### Positive

- Agent 对网络环境要求低，仅需出站访问。
- Backend 无需维护到每台服务器的连接。
- 易于扩展到多服务器。

### Negative

- Agent 需实现重试与离线处理。
- Backend 需处理重复上报与时间归一化。
- 实时性依赖上报周期。
