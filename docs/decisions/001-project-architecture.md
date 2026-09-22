# ADR-001: 项目整体架构

## Status

Accepted

## Context

需要一个面向中小规模 Linux 服务器的轻量级运维监控平台，兼顾监控、告警、服务管理与部署便捷性。服务器可能位于 NAT/防火墙环境，且希望平台可移植、易部署。

## Decision

采用 **前后端分离 + Agent/Server 架构**：

- Frontend：Vue 3 SPA，经 Nginx 同源访问后端。
- Backend：FastAPI，负责认证、资产、监控查询、告警引擎与任务引擎。
- Agent：部署在被监控服务器，主动向 Backend 上报/轮询。
- Database：MySQL 8 存储；Redis 用于缓存/任务状态。
- Deployment：平台以 Docker Compose 部署；Agent 以 systemd 原生部署。

## Alternatives

### 单体应用（后端渲染页面）

- 优点：部署简单、无前后端分离成本。
- 缺点：前端交互与可视化能力受限；不利于独立演进。

### Agent 以容器部署为主

- 优点：分发统一。
- 缺点：容器命名空间限制宿主指标采集与 systemd 服务控制，需特权与挂载，安全与复杂度更高。

## Consequences

### Positive

- 前后端与 Agent 职责清晰，可独立演进。
- 平台容器化、Agent 原生，兼顾可移植性与宿主能力。
- 为接入 Prometheus/Kubernetes 预留扩展空间。

### Negative

- 组件增多，部署与联调成本上升。
- 需要维护前后端与 Agent 三套构建/测试。
