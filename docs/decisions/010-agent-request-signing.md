# ADR-010: Agent 请求签名与防重放

## Status

Proposed（设计已定，待实现）

## Context

平台与 Agent 之间有两类凭证：用户 JWT 与 Agent Bearer Token（[ADR-003](003-authentication.md)）。Agent Token 仅存 SHA-256 哈希 + 前缀，明文仅返回一次。

Agent 是高权限组件（读取系统信息、受控启停服务、执行任务）。当前仅靠 Bearer Token 认证，缺少：

- 请求完整性校验（防篡改）；
- 防重放；
- 降低 Token 泄露/中间人捕获后的滥用面。

关键约束：**HMAC 对称签名要求服务端持有原始密钥用于验签**，而现有 Token 只存哈希，无法验签；且平台默认可能运行在内网 HTTP 之上。

## Problem

在只存 Token 哈希的前提下，为 Agent 请求增加完整性校验与防重放，并兼容存量 Agent 平滑上线。

## Options

### A. 对称 HMAC + 服务端可逆存储签名密钥

生成独立 `signing_secret`，后端用应用密钥（如 `SIGNING_SECRET_KEY`）加密存储，验签时解密。

- 优点：实现直接，验签快。
- 缺点：服务端必须**可逆保存**密钥，扩大泄露面；安装命令需额外下发密钥；需引入加密库。

### B. 非对称 Ed25519（选择）

Agent 本地生成 Ed25519 密钥对：私钥落盘（权限 600），注册时（Bearer 保护）上报公钥；后端按 server 绑定并存储公钥。请求用私钥签名，后端用公钥验签。

- 优点：无需分发/可逆存储对称密钥；公钥泄露无害；跨语言标准（Go 标准库、Python `cryptography`）。
- 缺点：注册流程扩展；旧 Agent 需升级；需配合防重放。

### C. 仅依赖 TLS + Token

- 优点：零改动。
- 缺点：不满足完整性与防重放要求，内网 HTTP 下风险高。

## Decision

采用 **B. Ed25519 请求签名**，并配合 **时间戳 + Request-Id + Redis 防重放**：

- Agent 首次运行生成密钥对，私钥持久化；注册请求携带 `signing_public_key`。
- 后端在 `ops_agent_token` 保存公钥，验签使用公钥。
- 灰度开关 `AGENT_REQUIRE_SIGNATURE`（默认 `false`）控制强制签名。

### 签名协议

请求头：

- `X-Agent-Id`：server_code
- `X-Timestamp`：Unix 秒
- `X-Request-Id`：uuid4
- `X-Signature`：Ed25519(canonical) 的 base64url

canonical string：

```text
{METHOD}\n{PATH}\n{TIMESTAMP}\n{REQUEST_ID}\n{SHA256_HEX(body)}
```

- `PATH` 为请求路径（query 处理见「开放问题」）。
- `body` 为原始字节的 SHA-256 十六进制；空 body 使用 `SHA256("")`。

### 校验顺序（所有 Agent 接口）

1. Bearer Token 有效（现有 `deps.get_agent_server`）。
2. `X-Agent-Id` 与 Token 绑定 server 的 `server_code` 一致。
3. `|now - timestamp| ≤ AGENT_SIGNATURE_MAX_SKEW`（默认 300s）。
4. `request_id` 未使用过：Redis `SET agent:sig:{server_id}:{request_id} 1 NX EX {2*skew}` 成功；失败判为重放。
5. 用存储的公钥验证 canonical 签名。
6. 任一失败返回 401（错误码见下）。

当 `AGENT_REQUIRE_SIGNATURE=false` 时：缺失签名的请求放行（兼容旧 Agent）；**提供了签名则仍校验**。开启后：缺失或错误签名一律拒绝。

### 数据模型（迁移 0003）

`ops_agent_token` 新增：

- `signing_public_key VARCHAR(128) NULL`：base64 编码的 Ed25519 公钥。
- `signing_algorithm VARCHAR(16) NULL DEFAULT 'ed25519'`。
- `key_registered_at DATETIME(3) NULL`。

### 配置

- `AGENT_REQUIRE_SIGNATURE: bool = False`
- `AGENT_SIGNATURE_MAX_SKEW: int = 300`

（方案 B 不需要服务端签名密钥。）

### 错误码（`error_codes.py`）

- `AGENT_SIGNATURE_INVALID = 40104`
- `AGENT_REQUEST_REPLAYED = 40105`
- `AGENT_SIGNATURE_MISSING = 40106`
- `AGENT_TIMESTAMP_INVALID = 40107`

### 注册流程

- `RegisterRequest` 增可选 `signing_public_key`。
- Agent 首次注册发送公钥，后端写入对应 Token 行。
- 已有 Token 但无公钥：首次带公钥注册时补写，且**仅当该 Token 尚无公钥**时写入（防止覆盖/劫持）。

### 实现落点

- 后端：对 `/api/v1/agent/*`（排除 `/package`、`/install.sh`）验签；`core/signing.py`（canonical + Ed25519 verify）；中间件或依赖需读取**原始 body**；`repositories/server_repository.py`、`services/agent_service.py`、`schemas/agent.py`、`core/config.py`、`exceptions/error_codes.py`；迁移 `0003`。
- Agent Python：密钥生成/加载、`reporter/client.py` 注入签名头、`config/config.py`、`install.sh`（密钥在目标机生成，无需新增安装参数）。
- Agent Go：`internal/signer`（`crypto/ed25519`）、`internal/reporter/client.go`、`internal/config`。
- 前端：无需改安装命令（密钥本地生成）。
- 文档：`reference/agent-protocol.md`、`architecture/security.md`、`operations/agent-deployment.md`、`reference/configuration.md`。

### 兼容与灰度

1. 阶段 1：后端接受并存储公钥，不强制（`AGENT_REQUIRE_SIGNATURE=false`）。
2. 阶段 2：新 Agent 默认签名；后端对已注册公钥的请求强校验。
3. 阶段 3：运维开启 `AGENT_REQUIRE_SIGNATURE=true`，拒绝无签名请求。

旧 Agent（无签名）在阶段 1/2 仍可用。

### 防重放与 Redis

- `AGENT_REQUIRE_SIGNATURE=true` 且 Redis 不可用：**拒绝**请求，不降级放行。
- 键 TTL = `2 × skew`，覆盖时钟窗口。

## Consequences

### Positive

- 请求完整性、防重放，降低 Token 泄露后的滥用面。
- 服务端无需可逆存储密钥。

### Negative

- 旧 Agent 需升级；每次请求增加验签开销（Ed25519 较快）。
- 依赖 Redis 做重放缓存；需节点时钟同步。
- PATH/query 规范化需谨慎。

## Open Questions

- 是否所有 Agent 接口都强制签名，还是仅写操作？**建议全部**（除注册首跳）。
- query 参数是否纳入 canonical（若纳入需定义排序规则）。
- 公钥轮换与 Token 撤销联动：撤销 Token 即失效对应公钥，是否需支持在线轮换？
- Agent 私钥落盘位置与权限：建议 `/opt/ops-agent/etc/agent_ed25519.key`，`0600`。
- 时钟偏差上限是否按环境可配。

## References

- [ADR-003 认证方案](003-authentication.md)
- [docs/architecture/security.md](../architecture/security.md)
- [docs/reference/agent-protocol.md](../reference/agent-protocol.md)
