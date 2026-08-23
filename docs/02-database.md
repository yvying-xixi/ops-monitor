# 数据库设计

> 建表脚本：`sql/ops_monitor_schema.sql`（MySQL 8.0，utf8mb4）
> 设计原则：监控数据与业务数据分离；密码、Agent Token 仅保存哈希；时间字段使用 `DATETIME(3)`，应用层统一使用 UTC。

## 一、表总览（26 张）

| 域 | 表 |
| --- | --- |
| 用户与权限 | `sys_user`、`sys_role`、`sys_permission`、`sys_user_role`、`sys_role_permission` |
| 服务器资产与 Agent | `ops_server`、`ops_server_disk`、`ops_server_network`、`ops_agent_token`、`ops_agent_heartbeat`、`ops_server_service`、`ops_server_container` |
| 监控指标 | `monitor_server_metric`、`monitor_disk_metric`、`monitor_network_metric`、`monitor_container_metric`、`monitor_process_snapshot` |
| 告警管理 | `alert_rule`、`alert_event`、`alert_event_log` |
| 自动化任务 | `ops_task`、`ops_task_target`、`ops_task_execution`、`ops_task_log` |
| 登录与审计 | `sys_login_log`、`sys_operation_log` |

## 二、用户与权限

### sys_user 系统用户表
`id` PK、`username` UNIQUE、`password_hash`、`nickname`、`email`、`phone`、`status`（0禁用/1启用）、`last_login_at/ip`、`created_at/updated_at`、`deleted_at`（软删除）
索引：`uk_username`、`uk_email`、`idx_status`、`idx_deleted_at`

### sys_role 角色表
`id` PK、`role_code` UNIQUE（如 `SYSTEM_ADMIN` / `OPS_ENGINEER` / `NORMAL_USER`）、`role_name`、`description`、`status`

### sys_permission 权限表
`id` PK、`permission_code` UNIQUE、`permission_name`、`permission_type`（MENU/API/BUTTON）、`path`、`method`、`parent_id`（自引用）、`status`

### sys_user_role / sys_role_permission
多对多关联表，联合主键 `(user_id, role_id)` / `(role_id, permission_id)`，外键级联自 `sys_user`、`sys_role`、`sys_permission`。

## 三、服务器资产与 Agent

### ops_server 服务器资产表
`id` PK、`server_code` UNIQUE、`hostname`、`ip_address` + `ssh_port` UNIQUE、`os_name/version`、`kernel_version`、`architecture`、`cpu_model`、`cpu_cores`、`memory_total_bytes`、`disk_total_bytes`、`agent_version`、`agent_status`（ONLINE/WARNING/OFFLINE/UNKNOWN）、`last_heartbeat_at`、`registered_at`、`status`、`remark`、`created_by` → sys_user、`deleted_at`
索引：`idx_agent_status`、`idx_last_heartbeat`、`idx_status`、`idx_hostname`

### ops_server_disk / ops_server_network
磁盘与网卡资产，均以 `server_id` 外键关联 `ops_server`，唯一键 `(server_id, device_name, mount_point)` / `(server_id, interface_name)`。

### ops_agent_token Agent 鉴权 Token 表
`id` PK、`server_id` → ops_server、`token_name`、`token_prefix`（识别用）、`token_hash`（SHA-256 哈希，不保存明文）、`status`（0撤销/1有效）、`expires_at`、`last_used_at`、`revoked_at`

### ops_agent_heartbeat 心跳历史表
`server_id` → ops_server、`agent_version`、`ip_address`、`collected_at`（Agent 侧时间）、`received_at`（服务端接收时间）
索引：`idx_server_time(server_id, collected_at)`

### ops_server_service 服务资产表
`server_id` → ops_server、`service_name` UNIQUE `(server_id, service_name)`、`display_name`、`service_type`（SYSTEMD/DOCKER/CUSTOM）、`is_whitelisted`（是否允许受控操作）、`is_critical`、`current_status`、`last_checked_at`

### ops_server_container 容器资产表
`server_id` → ops_server、`container_id` UNIQUE `(server_id, container_id)`、`container_name`、`image_name`、`container_status`、`restart_count`、`is_critical`、`last_seen_at`

## 四、监控指标

> 高频数据独立存储，与业务数据物理隔离。查询监控历史使用联合索引 `(server_id, collected_at)`。

### monitor_server_metric 服务器指标表（核心）
`id` PK、`server_id` → ops_server、`collected_at`
指标字段：`cpu_usage`、`memory_usage`、`memory_used_bytes`、`disk_usage`、`network_in_bytes`、`network_out_bytes`（累计值）、`load_1m/5m/15m`、`tcp_connections`、`uptime_seconds`
索引：`idx_server_time(server_id, collected_at)`、`idx_collected_at`

### monitor_disk_metric 磁盘指标表
`disk_id` → ops_server_disk、`server_id`、`collected_at`、`used_bytes`、`total_bytes`、`usage_percent`、`read_bytes`、`write_bytes`

### monitor_network_metric 网卡指标表
`network_id` → ops_server_network、`server_id`、`collected_at`、`bytes_received/sent`、`packets_received/sent`、`errors_received/sent`

### monitor_container_metric 容器指标表
`container_asset_id` → ops_server_container、`server_id`、`container_id`（快照）、`container_status`、`cpu_usage`、`memory_usage`、`memory_used_bytes`、`network_in_bytes`、`network_out_bytes`、`restart_count`

### monitor_process_snapshot 进程快照表
`server_id`、`process_pid`、`process_name`、`username`、`cpu_percent`、`memory_percent`、`memory_bytes`、`process_status`、`command_line`（注意脱敏）
索引：`idx_server_time`、`idx_server_pid_time`

## 五、告警管理

### alert_rule 告警规则表
`id` PK、`rule_name`、`metric_type`（CPU/MEMORY/DISK/LOAD/AGENT/SERVICE/CONTAINER）、`target_type`（SERVER/DISK/CONTAINER/SERVICE）、`severity`（WARNING/CRITICAL）、`operator`（GT/GTE/LT/LTE/EQ）、`threshold`、`duration_seconds`（持续异常时间）、`recovery_threshold`、`enabled`、`description`、`created_by` → sys_user

### alert_event 告警事件表
`id` PK、`rule_id` → alert_rule、`server_id`、`resource_type`、`resource_id`、`alert_key`（告警指纹）、`metric_type`、`severity`、`status`（PENDING/FIRING/ACKNOWLEDGED/RESOLVED）、`is_active`（生成列：PENDING/FIRING/ACKNOWLEDGED 时置 1，否则 NULL）、`first_fired_at`、`last_fired_at`、`acknowledged_by/at`、`resolved_at`、`current_value`、`threshold_value`、`message`
索引：`uk_alert_event_active_key(alert_key, is_active)`（活动告警去重）、`idx_server_status`、`idx_status_time`

### alert_event_log 告警状态变化日志
`event_id` → alert_event、`old_status`、`new_status`、`current_value`、`message`、`operator_id`

### 告警状态机

```text
PENDING --> FIRING --> ACKNOWLEDGED --> RESOLVED
```

## 六、自动化任务

### ops_task 任务表
`id` PK、`task_name`、`task_type`（SERVICE_CHECK/SERVICE_ACTION/SHELL_LIMITED）、`action`（STATUS/START/STOP/RESTART）、`service_name`（白名单校验后）、`schedule_type`（ONCE/CRON）、`cron_expression`、`status`（CREATED/PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED）、`created_by` → sys_user、`started_at/finished_at`、`timeout_seconds`、`confirmation_required`、`confirmed_by/at`

### ops_task_target 任务目标表
`task_id` → ops_task、`server_id` → ops_server、`target_status`，联合唯一 `(task_id, server_id)`

### ops_task_execution 任务执行记录
`task_id`、`target_id`（唯一）、`server_id`、`status`、`exit_code`、`result_text`、`error_message`、`started_at/finished_at`、`duration_ms`

### ops_task_log 任务日志
`execution_id` → ops_task_execution、`log_level`、`log_content`

### 任务生命周期

```text
CREATED --> PENDING --> RUNNING --> SUCCESS
                    --> RUNNING --> FAILED
                    --> RUNNING --> TIMEOUT
```

## 七、登录与审计

### sys_login_log 登录日志
`user_id`、`username`（失败时可为空）、`login_ip`、`user_agent`、`login_status`（SUCCESS/FAILED/LOCKED）、`failure_reason`、`request_id`

### sys_operation_log 操作审计日志
`user_id`、`username`（快照）、`module`、`operation`、`http_method`、`request_path`、`target_type/id`、`server_id`、`request_ip`、`request_id`、`request_params`（JSON，**禁止记录密码和 Token**）、`result_status`、`error_message`、`duration_ms`

## 八、Agent 状态判定

按 `last_heartbeat_at` 与当前 UTC 时间差判定：

| 最后心跳时间 | 状态 |
| --- | --- |
| ≤ 30 秒 | ONLINE |
| 30 < 心跳 ≤ 90 秒 | WARNING |
| > 90 秒 | OFFLINE |

```sql
UPDATE ops_server
SET agent_status = CASE
    WHEN last_heartbeat_at >= UTC_TIMESTAMP(3) - INTERVAL 30 SECOND THEN 'ONLINE'
    WHEN last_heartbeat_at >= UTC_TIMESTAMP(3) - INTERVAL 90 SECOND THEN 'WARNING'
    ELSE 'OFFLINE'
END
WHERE status = 1 AND deleted_at IS NULL;
```

## 九、常用查询

```sql
-- 服务器最近一小时监控数据
SELECT *
FROM monitor_server_metric
WHERE server_id = ?
  AND collected_at >= UTC_TIMESTAMP(3) - INTERVAL 1 HOUR
ORDER BY collected_at ASC;

-- 当前活动告警
SELECT *
FROM alert_event
WHERE is_active = 1
ORDER BY created_at DESC;
```

## 十、初始化数据

`ops_monitor_schema.sql` 中**不创建默认管理员**，避免固定弱密码。角色初始化数据由应用启动时生成密码哈希后插入：

```sql
INSERT INTO sys_role (role_code, role_name, description)
VALUES
('SYSTEM_ADMIN', '系统管理员', '拥有系统全部管理权限'),
('OPS_ENGINEER', '运维人员', '负责服务器监控、告警和任务操作'),
('NORMAL_USER', '普通用户', '查看授权服务器和监控数据');
```
