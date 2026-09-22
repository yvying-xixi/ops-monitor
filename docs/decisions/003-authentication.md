# ADR-003: 认证方案

## Status

Accepted

## Context

系统包含两类主体：平台用户与 Agent。需要选择凭证类型、存储方式与生命周期管理。

## Decision

- **用户认证**：账号密码登录，签发单 Access Token（JWT，HS256），payload 含 `sub/iat/exp`，有效期 `JWT_EXPIRE_MINUTES`（默认 120 分钟）。密码以 bcrypt 哈希存储。
- **Agent 认证**：独立 Token，由平台生成，数据库仅存 SHA-256 哈希与前缀，明文仅返回一次；请求头 `Authorization: Bearer <token>`。
- 接口权限由 RBAC（用户→角色→权限）控制；Agent 接口绑定服务器。

## Alternatives

### Access + Refresh 双 Token

- 优点：可刷新、体验好。
- 缺点：实现与状态管理更复杂，当前规模无必要。

### Session + Cookie

- 优点：服务端可控。
- 缺点：前后端分离下跨域/状态管理更繁琐。

## Consequences

### Positive

- 实现简单，满足当前需求。
- Agent 与用户认证隔离，职责清晰。
- Token 明文不落库，降低泄露风险。

### Negative

- 单 Token 无法主动刷新，过期需重新登录。
- Token 撤销/轮换流程需后续补充。
