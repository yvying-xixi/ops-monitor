# 安全模型

## 认证

| 主体 | 机制 | 说明 |
| --- | --- | --- |
| 用户 | JWT（HS256，Bearer） | 登录签发，payload 含 `sub`/`iat`/`exp`；有效期 `JWT_EXPIRE_MINUTES`（默认 120 分钟） |
| Agent | 独立 Token | 平台生成，数据库仅存 SHA-256 哈希；`Authorization: Bearer <token>` 访问 `/api/v1/agent/*` |

## 授权

- RBAC：用户 → 角色 → 权限（多对多）。
- 接口级：`require_roles(*role_codes)` 校验角色交集，无权限返回 403。
- 默认角色：`SYSTEM_ADMIN`、`OPS_ENGINEER`、`NORMAL_USER`。

详见 [modules/authorization.md](../modules/authorization.md)。

## 凭证存储

- 用户密码：bcrypt 哈希（passlib），禁止明文。
- Agent Token：仅存 SHA-256 哈希与前缀，明文只在生成时返回一次。
- 操作日志 `request_params` 禁止记录密码与 Token。

## 命令执行安全

服务操作严格遵守：

```text
服务名白名单校验 → 角色权限校验 → 操作类型校验 → Agent 端二次校验 → 记录审计日志
```

- 禁止将用户输入拼接进 Shell 命令；Agent 端 `subprocess` 恒用参数列表、`shell=False`。
- 允许操作仅限 `STATUS/START/STOP/RESTART` 与日志抓取；服务须在资产表且 `is_whitelisted=1`。
- 高风险操作（START/STOP/RESTART）默认需二次确认。

## 传输与部署

- 生产建议启用 HTTPS（`deploy/config.yml` 的 `https` 段）。
- mysql/redis 不暴露宿主端口，仅在 Compose 内网访问。
- Agent 上报接口鉴权与绑定服务器（Token → server）。

## 审计

登录、服务器操作、服务操作、任务执行、告警确认、权限修改均落库审计。详见 [modules/audit.md](../modules/audit.md)。

## TODO

> **TODO**: 补充密钥轮换、Token 撤销流程与最小权限落地清单。
