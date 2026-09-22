# 操作审计

> 本文描述登录日志、操作日志与任务日志。

## 审计数据

| 表 | 内容 |
| --- | --- |
| `sys_login_log` | 登录成功/失败（用户名、IP、UA、状态、失败原因、请求 ID） |
| `sys_operation_log` | 操作审计（用户、模块、操作、方法、路径、目标、IP、脱敏参数、结果、耗时） |
| `alert_event_log` | 告警状态变化 |
| `ops_task_log` | 任务执行明细 |

## 操作日志中间件

`OperationLogMiddleware` 对 `/api/v1` 下受保护接口记录操作日志：

- 跳过：`/health`、`/auth/login`、`/api/v1/agent/*`、`/docs`、`/openapi.json`。
- 记录：请求 ID、用户、方法、路径、IP、查询参数、结果状态、耗时。
- `request_params` **禁止记录密码与 Token**。
- 使用独立 `SessionLocal` 写入，`try/except` 兜底，永不阻断业务请求。

## 请求上下文

`RequestContextMiddleware` 生成/透传 `X-Request-ID` 并 best-effort 解析当前用户，供审计与排障关联。

## 覆盖范围

登录、服务器增删改、服务操作、任务执行、告警确认/恢复、用户与权限修改。

## TODO

> **TODO**: 补充审计日志的保留策略与查询接口说明（当前仅落库）。
