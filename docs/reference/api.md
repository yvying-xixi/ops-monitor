# 接口参考

## 范围

本文描述 API 的通用约定。具体接口、请求参数和响应 Schema 以 FastAPI 自动生成的 OpenAPI 文档为准。

## OpenAPI 文档

运行中的后端提供：

- Swagger UI：`/docs`
- ReDoc：`/redoc`
- OpenAPI Schema：`/openapi.json`

> **待办**: 根据生产部署（经 Nginx 反代）确认对外访问路径。

## 基础地址

```text
/api/v1
```

## 认证

- 用户接口：`Authorization: Bearer <JWT>`，登录接口 `POST /api/v1/auth/login` 获取。
- Agent 接口：`Authorization: Bearer <Agent Token>`，Token 由平台生成。
- Agent 安装包/脚本下载为公开接口，支持 `runtime=python|go`（默认 `python`），非法值回退 `python`。

## 响应格式

所有接口返回统一结构：

```json
{ "code": 0, "message": "ok", "data": {} }
```

- `code=0` 表示成功；非 0 为业务错误码（见 [error-codes.md](error-codes.md)）。
- 列表接口 `data` 为 `{ "total": <int>, "items": [...] }`。

## 分页

- 请求参数：`page`（从 1 开始）、`page_size`（上限 100）。
- 响应：`{ total, items }`。

## 过滤与排序

- 过滤：按各接口文档声明的字段（如 `status`、`agent_status`、`severity`）。
- 排序：后端默认按主键/时间倒序；具体以 OpenAPI 为准。
- 空值过滤：前端请求层会自动剔除值为 `''`/`null`/`undefined` 的查询参数；后端对可空整型（如 `status`）也将空串按未传处理。

## 错误处理

- 参数校验失败：HTTP 400 + `code=40000`。
- 未认证/无权限：401/403；资源不存在：404；冲突：409；内部错误：500。
- 网关错误：后端未就绪时 Nginx 对 `/api/` 返回 HTTP 503 + `code=50300`（统一 JSON），前端对 `GET` 自动退避重试。
- 错误码与 HTTP 状态映射见 [error-codes.md](error-codes.md)。

## 幂等性

- 创建任务 `POST /api/v1/tasks`：支持 `Idempotency-Key` 请求头，同键返回既有任务（唯一约束）。
- Agent 任务结果回传 `POST /api/v1/agent/task/result`：对已结束 `execution_id` 幂等重放，返回既有结果。
- Agent 签名请求：`X-Request-Id` 在时间窗口内去重，防重放。
- 前端对网关错误重试时，`GET` 与**带 `Idempotency-Key` 的 POST** 才重试。

## 服务器发现（只读）

- `GET /api/v1/discovery/config`：发现功能开关、允许网段白名单与限制（仅 `SYSTEM_ADMIN`）。
- `POST /api/v1/discovery/scan`：在白名单 CIDR 内做端口 / SSH banner 探测（仅 `SYSTEM_ADMIN`），**不持有凭据、不远程安装**。
- 详见 [ADR-012](../decisions/012-read-only-server-discovery.md)。

## 日期与时间

- 后端时间字段使用 `DATETIME(3)`，应用层统一 **UTC naive**。
- Agent 上报时间会归一化为 UTC 存储。

## 兼容性

- 当前仅 `/api/v1`；新增字段保持向后兼容，破坏性变更需标注并提升平台版本。
- 平台/数据库/Agent 的升级、回滚与协议兼容见 [operations/upgrade.md](../operations/upgrade.md) 与 [agent-protocol.md](agent-protocol.md#兼容性)。
