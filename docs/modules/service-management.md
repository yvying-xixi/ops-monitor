# 服务管理

> 本文描述被监控服务器上的服务状态监控与受控操作。

## 服务状态监控

- Agent `collector/service.py` 通过 `systemctl is-active` 采集状态：`RUNNING`/`STOPPED`/`FAILED`/`UNKNOWN`。
- 上报 `POST /api/v1/agent/services`，后端按 `(server_id, service_name)` 幂等 upsert 到 `ops_server_service`。
- Agent 配置 `collect.services` 定义监控与受控服务白名单（默认 `nginx`/`docker`/`ssh`）。

## 受控操作

操作统一走任务引擎（异步），类型：

| action | 说明 |
| --- | --- |
| STATUS | `systemctl is-active`（只读） |
| START / STOP / RESTART | 受控操作，默认需二次确认 |
| LOGS | `journalctl` 抓取最近日志 |

## 安全约束（双端校验）

1. **服务白名单**：后端任务创建时校验服务在资产表且 `is_whitelisted=1`；Agent executor 执行前再次校验。
2. **操作类型白名单**：仅 STATUS/START/STOP/RESTART（LOGS 为抓日志）。
3. **禁 shell 拼接**：subprocess 恒用参数列表、`shell=False`。
4. **二次确认**：START/STOP/RESTART 默认 `confirmation_required=1`。
5. **角色权限**：操作限 admin/ops；Agent 回传接口用 Agent Token 鉴权并绑定服务器。

## 服务管理 API

| Method | Endpoint | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/api/v1/servers/{id}/services` | 服务列表与状态 | 登录 |
| PUT | `/api/v1/servers/{id}/services/{sid}/whitelist` | 设置操作白名单 | admin |

> 服务操作通过任务接口提交，见 [modules/automation.md](automation.md)。

## 前端

`server/detail.vue` 服务管理卡片：状态标签、启动/停止/重启（二次确认）、日志任务、admin 白名单开关。

## 相关文档

- [modules/automation.md](automation.md)
- [architecture/security.md](../architecture/security.md)
