# 阶段六 · 自动化运维

> 对应总体规划「六、自动化运维」：服务状态监控、受控服务管理、自动化任务与执行记录。
> 文档固化任务分发机制、安全约束与接口约定。

## 一、总体机制

```
服务状态 = 周期上报      Agent systemctl 采集 → POST /agent/services → ops_server_service
运维操作 = 任务引擎      后端建任务 → Agent 轮询领取 → 受控执行 → 回传结果 → 状态聚合
```

### 任务分发（Agent 轮询）

```
后端创建 ops_task + targets + executions
  → Agent 每 task_poll_interval(5s) GET /agent/tasks/pending
  → 后端 PENDING→RUNNING，返回 (execution_id, action, service_name, timeout)
  → Agent executor 白名单二次校验后执行 systemctl（subprocess 参数列表、禁 shell、超时）
  → POST /agent/task/result 回传
  → 后端更新 execution/task 状态，写 ops_task_log
```

## 二、服务状态监控

- Agent `collector/service.py`：`systemctl is-active` → RUNNING/STOPPED/FAILED/UNKNOWN
- 上报 `POST /agent/services`，后端按 `(server_id, service_name)` 幂等 upsert
- `GET /servers/{id}/services` 查看；`PUT .../whitelist` 控制是否允许受控操作（admin）
- Agent 配置 `collect.services` 定义监控与受控服务白名单（默认 nginx/docker/ssh）

## 三、任务模型与状态机

```
CREATED(待确认) → PENDING(等待领取) → RUNNING(执行中) → SUCCESS
                              ├→ FAILED
                              ├→ TIMEOUT（超时扫描，30s）
                              └→ CANCELLED（取消未执行）
```

- task.status 由 executions 聚合：任一活跃→RUNNING；任一 FAILED/TIMEOUT→FAILED；全 SUCCESS→SUCCESS
- 批量任务：每台服务器独立 execution，前端展示独立结果

### 任务类型与操作

| task_type | action | 说明 |
| --- | --- | --- |
| SERVICE_CHECK | STATUS | systemctl is-active，只读 |
| SERVICE_ACTION | START/STOP/RESTART | 受控操作，默认需二次确认 |
| SERVICE_LOG | LOGS | journalctl -n 200 日志 |

## 四、安全约束（双端校验）

1. **服务白名单**：后端任务创建校验服务在资产表且 `is_whitelisted=1`；Agent executor 执行前再次校验
2. **操作类型白名单**：仅 STATUS/START/STOP/RESTART（LOGS 为抓日志）
3. **禁 shell 拼接**：subprocess 恒用参数列表、`shell=False`；杜绝注入
4. **二次确认**：START/STOP/RESTART 默认 `confirmation_required=1`，任务 CREATED 待 `POST /tasks/{id}/confirm` 放行
5. **角色权限**：任务操作限 SYSTEM_ADMIN/OPS_ENGINEER；回传接口用 Agent Token 鉴权并绑定服务器

## 五、接口

| 方法与路径 | 说明 | 权限 |
| --- | --- | --- |
| `GET /api/v1/tasks` | 任务分页列表 | admin/ops |
| `POST /api/v1/tasks` | 创建任务（单机/批量/定时） | admin/ops |
| `GET /api/v1/tasks/{id}` | 详情（各服务器执行结果+日志） | admin/ops |
| `POST /api/v1/tasks/{id}/confirm` | 二次确认 | admin/ops |
| `POST /api/v1/tasks/{id}/cancel` | 取消 | admin/ops |
| `GET /api/v1/agent/tasks/pending` | Agent 轮询领取 | Agent Token |
| `POST /api/v1/agent/task/result` | Agent 回传结果 | Agent Token |
| `GET /api/v1/servers/{id}/services` | 服务列表 | 登录 |
| `PUT /api/v1/servers/{id}/services/{sid}/whitelist` | 操作白名单 | admin |

## 六、定时任务（CRON）

- `schedule_type=CRON` + `cron_expression`（5 字段）
- 创建即 CREATED，确认后 PENDING；调度器每 30s 用 croniter 计算到期，触发时生成执行批次
- **当前为单次触发**：触发一次执行完成后任务结束；周期性多轮执行需后续任务行级 schema 迭代（`ops_task_target/execution` 存在 `(task_id, target_id)` 唯一约束）

## 七、前端

- `views/task/index.vue`：任务中心（列表/新建：类型-操作-多服务器-定时、确认/取消、详情含各服务器执行日志）
- `server/detail.vue`：服务管理卡片（状态标签、启动/停止/重启二次确认、日志任务、admin 白名单开关）

## 八、测试

- 后端：`test_services_api.py`、`test_task_api.py`、`test_task_dispatcher.py`（领取-回传-聚合/批处理/超时/CRON/重复回传）
- Agent：`test_service_collector.py`、`test_executor.py`（白名单/禁 shell/超时）、`test_worker.py`
- E2E：`test_task_e2e.py`（真实 uvicorn + 真实 Agent worker 执行 STATUS 只读任务 → 断言 SUCCESS + 日志落库 + 自清理）
