# API Reference

## Scope

本文描述 API 的通用约定。具体接口、请求参数和响应 Schema 以 FastAPI 自动生成的 OpenAPI 文档为准。

## OpenAPI Documentation

运行中的后端提供：

- Swagger UI：`/docs`
- ReDoc：`/redoc`
- OpenAPI Schema：`/openapi.json`

> **TODO**: 根据生产部署（经 Nginx 反代）确认对外访问路径。

## Base URL

```text
/api/v1
```

## Authentication

- 用户接口：`Authorization: Bearer <JWT>`，登录接口 `POST /api/v1/auth/login` 获取。
- Agent 接口：`Authorization: Bearer <Agent Token>`，Token 由平台生成。

## Response Format

所有接口返回统一结构：

```json
{ "code": 0, "message": "ok", "data": {} }
```

- `code=0` 表示成功；非 0 为业务错误码（见 [error-codes.md](error-codes.md)）。
- 列表接口 `data` 为 `{ "total": <int>, "items": [...] }`。

## Pagination

- 请求参数：`page`（从 1 开始）、`page_size`（上限 100）。
- 响应：`{ total, items }`。

## Filtering and Sorting

- 过滤：按各接口文档声明的字段（如 `status`、`agent_status`、`severity`）。
- 排序：后端默认按主键/时间倒序；具体以 OpenAPI 为准。

## Error Handling

- 参数校验失败：HTTP 400 + `code=40000`。
- 未认证/无权限：401/403；资源不存在：404；冲突：409；内部错误：500。
- 错误码与 HTTP 状态映射见 [error-codes.md](error-codes.md)。

## Idempotency

> **TODO**: 补充需要幂等处理的请求（如 Agent 上报、任务结果回传）及幂等键规则。

## Date and Time

- 后端时间字段使用 `DATETIME(3)`，应用层统一 **UTC naive**。
- Agent 上报时间会归一化为 UTC 存储。

## Compatibility

> **TODO**: 补充 API 版本演进与破坏性变更策略（当前仅 `/api/v1`）。
