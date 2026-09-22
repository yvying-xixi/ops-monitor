# 数据库 Reference

> 建表脚本：`sql/ops_monitor_schema.sql`（MySQL 8.0，utf8mb4）。
> 设计原则：监控数据与业务数据分离；密码与 Agent Token 仅存哈希；时间字段使用 `DATETIME(3)`，应用层统一 UTC。

## 表总览（26 张）

| 域 | 表 |
| --- | --- |
| 用户与权限 | `sys_user`、`sys_role`、`sys_permission`、`sys_user_role`、`sys_role_permission` |
| 服务器资产与 Agent | `ops_server`、`ops_server_disk`、`ops_server_network`、`ops_agent_token`、`ops_agent_heartbeat`、`ops_server_service`、`ops_server_container` |
| 监控指标 | `monitor_server_metric`、`monitor_disk_metric`、`monitor_network_metric`、`monitor_container_metric`、`monitor_process_snapshot` |
| 告警管理 | `alert_rule`、`alert_event`、`alert_event_log` |
| 自动化任务 | `ops_task`、`ops_task_target`、`ops_task_execution`、`ops_task_log` |
| 登录与审计 | `sys_login_log`、`sys_operation_log` |

## sys_user

系统用户。

### Purpose

存储平台用户账号，供登录与权限分配。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| username | varchar(64) | No | 登录用户名（唯一） |
| password_hash | varchar(255) | No | bcrypt 哈希 |
| nickname / email / phone | varchar | Yes | 资料 |
| status | tinyint | No | 0 禁用 / 1 启用 |
| last_login_at / last_login_ip | datetime(3) / varchar | Yes | 最后登录 |
| created_at / updated_at / deleted_at | datetime(3) | No/Yes | 时间与软删除 |

### Indexes

| Name | Columns | Purpose |
| --- | --- | --- |
| uk_sys_user_username | username | 登录查询唯一 |
| uk_sys_user_email | email | 邮箱唯一 |
| idx_sys_user_status | status | 状态过滤 |
| idx_sys_user_deleted_at | deleted_at | 软删除过滤 |

### Relations

- 与 `sys_role` 经 `sys_user_role` 多对多。

### Lifecycle

- 创建：管理员创建或种子初始化。
- 删除：软删除（置 `deleted_at`）。

### Related APIs

- `GET/POST /api/v1/users`、`GET/PUT/DELETE /api/v1/users/{id}`

## ops_server

服务器资产。

### Purpose

登记被监控服务器及其 Agent 状态。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| server_code | varchar(64) | No | 唯一编码（Agent 注册匹配键） |
| hostname / ip_address | varchar | No | 主机名 / IP |
| ssh_port | smallint unsigned | No | SSH 端口（默认 22） |
| os_name/os_version/kernel_version/architecture | varchar | Yes | 系统信息 |
| cpu_model / cpu_cores / memory_total_bytes / disk_total_bytes | — | Yes | 资源 |
| agent_version | varchar(32) | Yes | Agent 版本 |
| agent_status | varchar(16) | No | ONLINE/WARNING/OFFLINE/UNKNOWN |
| last_heartbeat_at / registered_at | datetime(3) | Yes | 心跳/注册 |
| status / remark / created_by / deleted_at | — | — | 资产状态/备注/创建人/软删除 |

### Indexes

`uk_ops_server_code(server_code)`、`uk_ops_server_ip_port(ip_address, ssh_port)`、`idx_ops_server_agent_status`、`idx_ops_server_last_heartbeat`、`idx_ops_server_status`、`idx_ops_server_hostname`

### Relations

- 1:N：磁盘、网卡、服务、容器、Token、心跳、指标。
- N:1：`created_by` → `sys_user`。

### Lifecycle

- 创建：管理员预创建；Agent 注册回写系统信息并置 ONLINE。
- 状态：由心跳驱动刷新。
- 删除：软删除。

### Related APIs

- `GET/POST /api/v1/servers`、`GET /api/v1/servers/{id}`、`POST /api/v1/servers/{id}/agent-token`

## ops_agent_token

Agent 鉴权凭证。

### Purpose

为服务器签发 Agent 注册/上报凭证，仅存哈希。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| server_id | bigint unsigned | No | 所属服务器 |
| token_prefix | varchar(16) | No | 前缀（识别） |
| token_hash | char(64) | No | SHA-256 哈希（唯一） |
| status | tinyint | No | 0 撤销 / 1 有效 |
| expires_at / last_used_at / revoked_at | datetime(3) | Yes | 生命周期 |

### Indexes

`uk_ops_agent_token_hash(token_hash)`、`idx_ops_agent_token_server_status(server_id, status)`

### Relations

- N:1：`server_id` → `ops_server`。

### Lifecycle

- 创建：管理员为服务器生成，明文仅返回一次。
- 撤销：置 `status=0` 与 `revoked_at`。

### Related APIs

- `POST /api/v1/servers/{id}/agent-token`

## monitor_server_metric

服务器监控指标（核心，高频追加）。

### Purpose

存储 Agent 上报的服务器指标，支撑实时展示与历史趋势。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| server_id | bigint unsigned | No | 服务器 |
| collected_at | datetime(3) | No | 采集时间 |
| cpu_usage / memory_usage / disk_usage | decimal(5,2) | Yes | 使用率（%） |
| memory_used_bytes / network_in_bytes / network_out_bytes / uptime_seconds | bigint unsigned | Yes | 内存/网络/运行时长 |
| load_1m / load_5m / load_15m | decimal(10,2) | Yes | Load |
| tcp_connections | int unsigned | Yes | TCP 连接数 |

### Indexes

`idx_monitor_server_metric_server_time(server_id, collected_at)`、`idx_monitor_server_metric_collected_at(collected_at)`

### Relations

- N:1：`server_id` → `ops_server`。

### Lifecycle

- 追加写入；按 `METRIC_RETENTION_DAYS` 定期清理。

### Related APIs

- `GET /api/v1/servers/{id}/metrics/latest|history|summary`

## alert_event

告警事件。

### Purpose

记录告警活动状态与历史，供确认/恢复与展示。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| rule_id | bigint unsigned | No | 规则 |
| server_id | bigint unsigned | Yes | 服务器 |
| alert_key | varchar(255) | No | 告警指纹（去重） |
| metric_type / severity / status | varchar | No | 指标/级别/状态 |
| is_active | tinyint | Yes | 生成列：活动状态为 1，否则 NULL |
| first_fired_at / last_fired_at / acknowledged_at / resolved_at | datetime(3) | Yes | 时间线 |
| current_value / threshold_value | decimal(12,4) | Yes | 值/阈值 |
| message | varchar(500) | No | 消息 |

### Indexes

`uk_alert_event_active_key(alert_key, is_active)`（活动去重）、`idx_alert_event_server_status`、`idx_alert_event_status_time`

### Relations

- N:1：`rule_id` → `alert_rule`；`server_id` → `ops_server`；`acknowledged_by` → `sys_user`。
- 1:N：`alert_event_log`。

### Lifecycle

- 由告警引擎按状态机创建/更新；恢复后 `is_active=NULL`。

### Related APIs

- `GET /api/v1/alerts`、`GET /api/v1/alerts/{id}`、`POST /api/v1/alerts/{id}/ack|resolve`

## ops_task

运维任务。

### Purpose

记录任务定义与聚合状态。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| task_name / task_type | varchar | No | 名称/类型 |
| action / service_name | varchar | Yes | 操作/服务 |
| schedule_type / cron_expression | varchar | — | ONCE/CRON |
| status | varchar(24) | No | CREATED/PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED |
| created_by | bigint unsigned | No | 创建人 |
| timeout_seconds / confirmation_required / confirmed_by / confirmed_at | — | — | 超时/确认 |

### Indexes

`idx_ops_task_creator_time`、`idx_ops_task_status`、`idx_ops_task_schedule`

### Relations

- 1:N：`ops_task_target` → `ops_task_execution` → `ops_task_log`。
- N:1：`created_by`/`confirmed_by` → `sys_user`。

### Lifecycle

- 创建 → 确认 → 领取 → 执行 → 聚合；超时扫描置 TIMEOUT。

### Related APIs

- `GET/POST /api/v1/tasks`、`GET /api/v1/tasks/{id}`、`POST /api/v1/tasks/{id}/confirm|cancel`

## sys_operation_log

操作审计日志。

### Purpose

记录用户操作，支持审计追溯。

### Columns

| Column | Type | Nullable | Description |
| --- | --- | ---: | --- |
| id | bigint unsigned | No | 主键 |
| user_id / username | bigint / varchar | Yes | 操作人 |
| module / operation | varchar | No | 模块/操作 |
| http_method / request_path | varchar | Yes | 请求 |
| target_type / target_id / server_id | — | Yes | 目标 |
| request_ip / request_id | varchar | Yes | 来源 |
| request_params | json | Yes | 参数（禁止密码/Token） |
| result_status / error_message / duration_ms | — | — | 结果/耗时 |

### Indexes

`idx_sys_operation_log_user_time`、`idx_sys_operation_log_server_time`、`idx_sys_operation_log_module_time`、`idx_sys_operation_log_status_time`、`idx_sys_operation_log_created_at`

### Relations

- N:1：`user_id` → `sys_user`；`server_id` → `ops_server`。

### Lifecycle

- 追加写入（中间件异步）。

### Related APIs

> **TODO**: 当前无对外查询接口，后续补充审计查询 API。

## 其余表（简列）

- `sys_role` / `sys_permission`：角色与权限；关联表 `sys_user_role`、`sys_role_permission`（联合主键）。
- `ops_server_disk` / `ops_server_network` / `ops_server_service` / `ops_server_container`：服务器子资产，均以 `server_id` 外键关联，按自然键唯一。
- `ops_agent_heartbeat`：心跳历史，`(server_id, collected_at)` 索引。
- `monitor_disk_metric` / `monitor_network_metric` / `monitor_container_metric` / `monitor_process_snapshot`：分项指标。
- `alert_rule` / `alert_event_log`：规则与状态日志。
- `ops_task_target` / `ops_task_execution` / `ops_task_log`：任务目标/执行/日志。
- `sys_login_log`：登录日志。

## Agent 状态判定

```sql
UPDATE ops_server
SET agent_status = CASE
    WHEN last_heartbeat_at >= UTC_TIMESTAMP(3) - INTERVAL 30 SECOND THEN 'ONLINE'
    WHEN last_heartbeat_at >= UTC_TIMESTAMP(3) - INTERVAL 90 SECOND THEN 'WARNING'
    ELSE 'OFFLINE'
END
WHERE status = 1 AND deleted_at IS NULL;
```

## 常用查询

```sql
-- 服务器最近一小时监控数据
SELECT * FROM monitor_server_metric
WHERE server_id = ? AND collected_at >= UTC_TIMESTAMP(3) - INTERVAL 1 HOUR
ORDER BY collected_at ASC;

-- 当前活动告警
SELECT * FROM alert_event WHERE is_active = 1 ORDER BY created_at DESC;
```

## TODO

> **TODO**: 补充索引与典型查询的执行计划验证结论。
> **TODO**: 补充监控数据的归档/分区策略。
