-- ============================================================
-- 轻量级服务器运维监控平台
-- MySQL 8.0 建表脚本
-- 说明：
-- 1. 监控数据与业务数据分离。
-- 2. 密码、Agent Token 仅保存哈希，不保存明文。
-- 3. 所有时间字段使用 DATETIME(3)，建议应用层统一使用 UTC。
-- 4. 执行前请确认当前账号具有 CREATE DATABASE、CREATE TABLE 权限。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ops_monitor
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE ops_monitor;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 删除旧表：便于开发环境重复执行
-- 生产环境执行前请先备份，并删除本段 DROP TABLE 语句
-- ============================================================

DROP TABLE IF EXISTS sys_operation_log;
DROP TABLE IF EXISTS sys_login_log;
DROP TABLE IF EXISTS alert_event_log;
DROP TABLE IF EXISTS ops_task_log;
DROP TABLE IF EXISTS ops_task_execution;
DROP TABLE IF EXISTS ops_task_target;
DROP TABLE IF EXISTS ops_task;
DROP TABLE IF EXISTS alert_event;
DROP TABLE IF EXISTS alert_rule;
DROP TABLE IF EXISTS monitor_process_snapshot;
DROP TABLE IF EXISTS monitor_container_metric;
DROP TABLE IF EXISTS monitor_network_metric;
DROP TABLE IF EXISTS monitor_disk_metric;
DROP TABLE IF EXISTS monitor_server_metric;
DROP TABLE IF EXISTS ops_server_container;
DROP TABLE IF EXISTS ops_server_service;
DROP TABLE IF EXISTS ops_agent_heartbeat;
DROP TABLE IF EXISTS ops_agent_token;
DROP TABLE IF EXISTS ops_server_network;
DROP TABLE IF EXISTS ops_server_disk;
DROP TABLE IF EXISTS ops_server;
DROP TABLE IF EXISTS sys_role_permission;
DROP TABLE IF EXISTS sys_user_role;
DROP TABLE IF EXISTS sys_permission;
DROP TABLE IF EXISTS sys_role;
DROP TABLE IF EXISTS sys_user;

-- ============================================================
-- 一、用户与权限
-- ============================================================

CREATE TABLE sys_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(64) NOT NULL COMMENT '登录用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    nickname VARCHAR(64) NULL COMMENT '用户昵称',
    email VARCHAR(128) NULL COMMENT '邮箱',
    phone VARCHAR(32) NULL COMMENT '手机号',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0禁用，1启用',
    last_login_at DATETIME(3) NULL COMMENT '最后登录时间',
    last_login_ip VARCHAR(64) NULL COMMENT '最后登录IP',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at DATETIME(3) NULL COMMENT '软删除时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_sys_user_username (username),
    UNIQUE KEY uk_sys_user_email (email),
    KEY idx_sys_user_status (status),
    KEY idx_sys_user_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='系统用户表';

CREATE TABLE sys_role (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '角色ID',
    role_code VARCHAR(64) NOT NULL COMMENT '角色编码',
    role_name VARCHAR(64) NOT NULL COMMENT '角色名称',
    description VARCHAR(255) NULL COMMENT '角色描述',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0禁用，1启用',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_sys_role_code (role_code),
    KEY idx_sys_role_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='系统角色表';

CREATE TABLE sys_permission (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '权限ID',
    permission_code VARCHAR(128) NOT NULL COMMENT '权限编码',
    permission_name VARCHAR(128) NOT NULL COMMENT '权限名称',
    permission_type VARCHAR(16) NOT NULL COMMENT '权限类型：MENU/API/BUTTON',
    path VARCHAR(255) NULL COMMENT '前端路由或接口路径',
    method VARCHAR(16) NULL COMMENT 'HTTP方法',
    parent_id BIGINT UNSIGNED NULL COMMENT '父权限ID',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0禁用，1启用',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_sys_permission_code (permission_code),
    KEY idx_sys_permission_parent_id (parent_id),
    KEY idx_sys_permission_type_status (permission_type, status),
    CONSTRAINT fk_sys_permission_parent
        FOREIGN KEY (parent_id) REFERENCES sys_permission(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='系统权限表';

CREATE TABLE sys_user_role (
    user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
    role_id BIGINT UNSIGNED NOT NULL COMMENT '角色ID',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, role_id),
    KEY idx_sys_user_role_role_id (role_id),
    CONSTRAINT fk_sys_user_role_user
        FOREIGN KEY (user_id) REFERENCES sys_user(id),
    CONSTRAINT fk_sys_user_role_role
        FOREIGN KEY (role_id) REFERENCES sys_role(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='用户角色关联表';

CREATE TABLE sys_role_permission (
    role_id BIGINT UNSIGNED NOT NULL COMMENT '角色ID',
    permission_id BIGINT UNSIGNED NOT NULL COMMENT '权限ID',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (role_id, permission_id),
    KEY idx_sys_role_permission_permission_id (permission_id),
    CONSTRAINT fk_sys_role_permission_role
        FOREIGN KEY (role_id) REFERENCES sys_role(id),
    CONSTRAINT fk_sys_role_permission_permission
        FOREIGN KEY (permission_id) REFERENCES sys_permission(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='角色权限关联表';

-- ============================================================
-- 二、服务器资产与 Agent
-- ============================================================

CREATE TABLE ops_server (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '服务器ID',
    server_code VARCHAR(64) NOT NULL COMMENT '服务器唯一编码',
    hostname VARCHAR(128) NOT NULL COMMENT '主机名',
    ip_address VARCHAR(64) NOT NULL COMMENT '服务器IP地址',
    ssh_port SMALLINT UNSIGNED NOT NULL DEFAULT 22 COMMENT 'SSH端口',
    os_name VARCHAR(128) NULL COMMENT '操作系统名称',
    os_version VARCHAR(128) NULL COMMENT '操作系统版本',
    kernel_version VARCHAR(128) NULL COMMENT '内核版本',
    architecture VARCHAR(32) NULL COMMENT '系统架构',
    cpu_model VARCHAR(255) NULL COMMENT 'CPU型号',
    cpu_cores INT UNSIGNED NULL COMMENT 'CPU逻辑核心数',
    memory_total_bytes BIGINT UNSIGNED NULL COMMENT '内存总量，单位：字节',
    disk_total_bytes BIGINT UNSIGNED NULL COMMENT '磁盘总量，单位：字节',
    agent_version VARCHAR(32) NULL COMMENT 'Agent版本',
    agent_status VARCHAR(16) NOT NULL DEFAULT 'OFFLINE'
        COMMENT 'Agent状态：ONLINE/WARNING/OFFLINE/UNKNOWN',
    last_heartbeat_at DATETIME(3) NULL COMMENT '最后心跳时间',
    registered_at DATETIME(3) NULL COMMENT 'Agent注册时间',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '资产状态：0停用，1启用',
    remark VARCHAR(500) NULL COMMENT '备注',
    created_by BIGINT UNSIGNED NULL COMMENT '创建人',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at DATETIME(3) NULL COMMENT '软删除时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_server_code (server_code),
    UNIQUE KEY uk_ops_server_ip_port (ip_address, ssh_port),
    KEY idx_ops_server_agent_status (agent_status),
    KEY idx_ops_server_last_heartbeat (last_heartbeat_at),
    KEY idx_ops_server_status (status),
    KEY idx_ops_server_hostname (hostname),
    CONSTRAINT fk_ops_server_created_by
        FOREIGN KEY (created_by) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='服务器资产表';

CREATE TABLE ops_server_disk (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '磁盘资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    device_name VARCHAR(128) NOT NULL COMMENT '设备名称',
    mount_point VARCHAR(255) NULL COMMENT '挂载点',
    filesystem VARCHAR(64) NULL COMMENT '文件系统',
    total_bytes BIGINT UNSIGNED NULL COMMENT '磁盘总量，单位：字节',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0停用，1启用',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_server_disk (server_id, device_name, mount_point),
    KEY idx_ops_server_disk_server_id (server_id),
    CONSTRAINT fk_ops_server_disk_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='服务器磁盘资产表';

CREATE TABLE ops_server_network (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '网卡资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    interface_name VARCHAR(128) NOT NULL COMMENT '网卡名称',
    mac_address VARCHAR(64) NULL COMMENT 'MAC地址',
    ip_address VARCHAR(64) NULL COMMENT '网卡IP地址',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0停用，1启用',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_server_network_interface (server_id, interface_name),
    KEY idx_ops_server_network_server_id (server_id),
    CONSTRAINT fk_ops_server_network_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='服务器网卡资产表';

CREATE TABLE ops_agent_token (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Token记录ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    token_name VARCHAR(64) NOT NULL COMMENT 'Token名称',
    token_prefix VARCHAR(16) NOT NULL COMMENT 'Token前缀，用于识别',
    token_hash CHAR(64) NOT NULL COMMENT 'Token哈希，不保存明文',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0撤销，1有效',
    expires_at DATETIME(3) NULL COMMENT '过期时间',
    last_used_at DATETIME(3) NULL COMMENT '最后使用时间',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    revoked_at DATETIME(3) NULL COMMENT '撤销时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_agent_token_hash (token_hash),
    KEY idx_ops_agent_token_server_status (server_id, status),
    CONSTRAINT fk_ops_agent_token_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Agent鉴权Token表';

CREATE TABLE ops_agent_heartbeat (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '心跳记录ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    agent_version VARCHAR(32) NULL COMMENT 'Agent版本',
    ip_address VARCHAR(64) NULL COMMENT 'Agent上报IP',
    collected_at DATETIME(3) NOT NULL COMMENT '心跳时间',
    received_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '服务端接收时间',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_ops_agent_heartbeat_server_time (server_id, collected_at),
    KEY idx_ops_agent_heartbeat_received_at (received_at),
    CONSTRAINT fk_ops_agent_heartbeat_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Agent心跳历史表';

CREATE TABLE ops_server_service (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '服务资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    service_name VARCHAR(64) NOT NULL COMMENT 'systemd服务名称',
    display_name VARCHAR(128) NULL COMMENT '展示名称',
    service_type VARCHAR(32) NOT NULL DEFAULT 'SYSTEMD' COMMENT 'SYSTEMD/DOCKER/CUSTOM',
    is_whitelisted TINYINT NOT NULL DEFAULT 1 COMMENT '是否允许执行受控操作',
    is_critical TINYINT NOT NULL DEFAULT 0 COMMENT '是否为关键服务',
    current_status VARCHAR(32) NULL COMMENT 'RUNNING/STOPPED/FAILED/UNKNOWN',
    last_checked_at DATETIME(3) NULL COMMENT '最后检查时间',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0停用，1启用',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_server_service (server_id, service_name),
    KEY idx_ops_server_service_status (server_id, current_status),
    KEY idx_ops_server_service_critical (is_critical, current_status),
    CONSTRAINT fk_ops_server_service_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='服务器服务资产表';

CREATE TABLE ops_server_container (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '容器资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    container_id VARCHAR(128) NOT NULL COMMENT '容器ID',
    container_name VARCHAR(255) NOT NULL COMMENT '容器名称',
    image_name VARCHAR(255) NULL COMMENT '镜像名称',
    container_status VARCHAR(32) NULL COMMENT 'RUNNING/STOPPED/PAUSED/EXITED',
    restart_count INT UNSIGNED NULL COMMENT '重启次数',
    container_created_at DATETIME(3) NULL COMMENT '容器创建时间',
    is_critical TINYINT NOT NULL DEFAULT 0 COMMENT '是否为关键容器',
    last_seen_at DATETIME(3) NULL COMMENT '最后发现时间',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0停用，1启用',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_server_container (server_id, container_id),
    KEY idx_ops_server_container_status (server_id, container_status),
    KEY idx_ops_server_container_critical (is_critical, container_status),
    CONSTRAINT fk_ops_server_container_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Docker容器资产表';

-- ============================================================
-- 三、监控指标
-- ============================================================

CREATE TABLE monitor_server_metric (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '指标记录ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    collected_at DATETIME(3) NOT NULL COMMENT '采集时间',
    cpu_usage DECIMAL(5,2) NULL COMMENT 'CPU使用率，百分比',
    memory_usage DECIMAL(5,2) NULL COMMENT '内存使用率，百分比',
    memory_used_bytes BIGINT UNSIGNED NULL COMMENT '已使用内存，单位：字节',
    disk_usage DECIMAL(5,2) NULL COMMENT '整体磁盘使用率，百分比',
    network_in_bytes BIGINT UNSIGNED NULL COMMENT '累计入站字节数',
    network_out_bytes BIGINT UNSIGNED NULL COMMENT '累计出站字节数',
    load_1m DECIMAL(10,2) NULL COMMENT '1分钟Load',
    load_5m DECIMAL(10,2) NULL COMMENT '5分钟Load',
    load_15m DECIMAL(10,2) NULL COMMENT '15分钟Load',
    tcp_connections INT UNSIGNED NULL COMMENT 'TCP连接数',
    uptime_seconds BIGINT UNSIGNED NULL COMMENT '系统运行时长，单位：秒',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_monitor_server_metric_server_time (server_id, collected_at),
    KEY idx_monitor_server_metric_collected_at (collected_at),
    CONSTRAINT fk_monitor_server_metric_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='服务器监控指标表';

CREATE TABLE monitor_disk_metric (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '磁盘指标记录ID',
    disk_id BIGINT UNSIGNED NOT NULL COMMENT '磁盘资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    collected_at DATETIME(3) NOT NULL COMMENT '采集时间',
    used_bytes BIGINT UNSIGNED NULL COMMENT '已使用容量，单位：字节',
    total_bytes BIGINT UNSIGNED NULL COMMENT '总容量，单位：字节',
    usage_percent DECIMAL(5,2) NULL COMMENT '使用率，百分比',
    read_bytes BIGINT UNSIGNED NULL COMMENT '累计读取字节数',
    write_bytes BIGINT UNSIGNED NULL COMMENT '累计写入字节数',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_monitor_disk_metric_disk_time (disk_id, collected_at),
    KEY idx_monitor_disk_metric_server_time (server_id, collected_at),
    CONSTRAINT fk_monitor_disk_metric_disk
        FOREIGN KEY (disk_id) REFERENCES ops_server_disk(id),
    CONSTRAINT fk_monitor_disk_metric_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='磁盘监控指标表';

CREATE TABLE monitor_network_metric (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '网卡指标记录ID',
    network_id BIGINT UNSIGNED NOT NULL COMMENT '网卡资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    collected_at DATETIME(3) NOT NULL COMMENT '采集时间',
    bytes_received BIGINT UNSIGNED NULL COMMENT '累计接收字节数',
    bytes_sent BIGINT UNSIGNED NULL COMMENT '累计发送字节数',
    packets_received BIGINT UNSIGNED NULL COMMENT '累计接收数据包数',
    packets_sent BIGINT UNSIGNED NULL COMMENT '累计发送数据包数',
    errors_received INT UNSIGNED NULL COMMENT '接收错误数',
    errors_sent INT UNSIGNED NULL COMMENT '发送错误数',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_monitor_network_metric_network_time (network_id, collected_at),
    KEY idx_monitor_network_metric_server_time (server_id, collected_at),
    CONSTRAINT fk_monitor_network_metric_network
        FOREIGN KEY (network_id) REFERENCES ops_server_network(id),
    CONSTRAINT fk_monitor_network_metric_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='网卡监控指标表';

CREATE TABLE monitor_container_metric (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '容器指标记录ID',
    container_asset_id BIGINT UNSIGNED NOT NULL COMMENT '容器资产ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    container_id VARCHAR(128) NOT NULL COMMENT '容器ID快照',
    container_status VARCHAR(32) NULL COMMENT 'RUNNING/STOPPED/PAUSED/EXITED',
    cpu_usage DECIMAL(7,3) NULL COMMENT 'CPU使用率',
    memory_usage DECIMAL(7,3) NULL COMMENT '内存使用率',
    memory_used_bytes BIGINT UNSIGNED NULL COMMENT '容器已使用内存',
    network_in_bytes BIGINT UNSIGNED NULL COMMENT '累计入站字节数',
    network_out_bytes BIGINT UNSIGNED NULL COMMENT '累计出站字节数',
    restart_count INT UNSIGNED NULL COMMENT '重启次数',
    collected_at DATETIME(3) NOT NULL COMMENT '采集时间',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_monitor_container_metric_asset_time (container_asset_id, collected_at),
    KEY idx_monitor_container_metric_server_time (server_id, collected_at),
    CONSTRAINT fk_monitor_container_metric_asset
        FOREIGN KEY (container_asset_id) REFERENCES ops_server_container(id),
    CONSTRAINT fk_monitor_container_metric_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Docker容器监控指标表';

CREATE TABLE monitor_process_snapshot (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '进程快照记录ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    process_pid INT UNSIGNED NOT NULL COMMENT '进程PID',
    process_name VARCHAR(255) NULL COMMENT '进程名称',
    username VARCHAR(128) NULL COMMENT '进程所属用户',
    cpu_percent DECIMAL(7,3) NULL COMMENT '进程CPU使用率',
    memory_percent DECIMAL(7,3) NULL COMMENT '进程内存使用率',
    memory_bytes BIGINT UNSIGNED NULL COMMENT '进程内存占用',
    process_status VARCHAR(32) NULL COMMENT '进程状态',
    command_line TEXT NULL COMMENT '命令行，注意脱敏',
    collected_at DATETIME(3) NOT NULL COMMENT '采集时间',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_monitor_process_snapshot_server_time (server_id, collected_at),
    KEY idx_monitor_process_snapshot_server_pid_time (server_id, process_pid, collected_at),
    CONSTRAINT fk_monitor_process_snapshot_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='服务器进程快照表';

-- ============================================================
-- 四、告警管理
-- ============================================================

CREATE TABLE alert_rule (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '告警规则ID',
    rule_name VARCHAR(128) NOT NULL COMMENT '规则名称',
    metric_type VARCHAR(64) NOT NULL COMMENT 'CPU/MEMORY/DISK/LOAD/AGENT/SERVICE/CONTAINER',
    target_type VARCHAR(32) NOT NULL DEFAULT 'SERVER' COMMENT 'SERVER/DISK/CONTAINER/SERVICE',
    severity VARCHAR(16) NOT NULL COMMENT 'WARNING/CRITICAL',
    operator VARCHAR(8) NOT NULL COMMENT 'GT/GTE/LT/LTE/EQ',
    threshold DECIMAL(12,4) NULL COMMENT '数值阈值',
    duration_seconds INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '持续异常时间，单位：秒',
    recovery_threshold DECIMAL(12,4) NULL COMMENT '恢复阈值，可为空',
    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    description VARCHAR(500) NULL COMMENT '规则描述',
    created_by BIGINT UNSIGNED NULL COMMENT '创建人',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_alert_rule_metric_enabled (metric_type, enabled),
    KEY idx_alert_rule_target_enabled (target_type, enabled),
    CONSTRAINT fk_alert_rule_created_by
        FOREIGN KEY (created_by) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='告警规则表';

CREATE TABLE alert_event (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '告警事件ID',
    rule_id BIGINT UNSIGNED NOT NULL COMMENT '告警规则ID',
    server_id BIGINT UNSIGNED NULL COMMENT '服务器ID',
    resource_type VARCHAR(32) NOT NULL DEFAULT 'SERVER' COMMENT '资源类型',
    resource_id BIGINT UNSIGNED NULL COMMENT '资源ID',
    alert_key VARCHAR(255) NOT NULL COMMENT '告警指纹，用于活动告警去重',
    metric_type VARCHAR(64) NOT NULL COMMENT '指标类型',
    severity VARCHAR(16) NOT NULL COMMENT 'WARNING/CRITICAL',
    status VARCHAR(24) NOT NULL DEFAULT 'PENDING'
        COMMENT 'PENDING/FIRING/ACKNOWLEDGED/RESOLVED',
    is_active TINYINT GENERATED ALWAYS AS
        (CASE WHEN status IN ('PENDING', 'FIRING', 'ACKNOWLEDGED') THEN 1 ELSE NULL END) STORED
        COMMENT '活动告警标记，用于唯一约束',
    first_fired_at DATETIME(3) NULL COMMENT '首次触发时间',
    last_fired_at DATETIME(3) NULL COMMENT '最近触发时间',
    acknowledged_by BIGINT UNSIGNED NULL COMMENT '确认人',
    acknowledged_at DATETIME(3) NULL COMMENT '确认时间',
    resolved_at DATETIME(3) NULL COMMENT '恢复时间',
    current_value DECIMAL(12,4) NULL COMMENT '当前指标值',
    threshold_value DECIMAL(12,4) NULL COMMENT '触发阈值',
    message VARCHAR(500) NOT NULL COMMENT '告警消息',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_alert_event_active_key (alert_key, is_active),
    KEY idx_alert_event_server_status (server_id, status),
    KEY idx_alert_event_status_time (status, created_at),
    KEY idx_alert_event_rule_id (rule_id),
    CONSTRAINT fk_alert_event_rule
        FOREIGN KEY (rule_id) REFERENCES alert_rule(id),
    CONSTRAINT fk_alert_event_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id),
    CONSTRAINT fk_alert_event_acknowledged_by
        FOREIGN KEY (acknowledged_by) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='告警事件表';

CREATE TABLE alert_event_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '告警事件日志ID',
    event_id BIGINT UNSIGNED NOT NULL COMMENT '告警事件ID',
    old_status VARCHAR(24) NULL COMMENT '原状态',
    new_status VARCHAR(24) NOT NULL COMMENT '新状态',
    current_value DECIMAL(12,4) NULL COMMENT '事件值',
    message VARCHAR(500) NULL COMMENT '状态变化说明',
    operator_id BIGINT UNSIGNED NULL COMMENT '操作人，系统操作可为空',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_alert_event_log_event_time (event_id, created_at),
    CONSTRAINT fk_alert_event_log_event
        FOREIGN KEY (event_id) REFERENCES alert_event(id),
    CONSTRAINT fk_alert_event_log_operator
        FOREIGN KEY (operator_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='告警状态变化日志表';

-- ============================================================
-- 五、自动化任务
-- ============================================================

CREATE TABLE ops_task (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务ID',
    task_name VARCHAR(128) NOT NULL COMMENT '任务名称',
    task_type VARCHAR(32) NOT NULL COMMENT 'SERVICE_CHECK/SERVICE_ACTION/SHELL_LIMITED',
    action VARCHAR(32) NULL COMMENT 'STATUS/START/STOP/RESTART',
    service_name VARCHAR(64) NULL COMMENT '经过白名单校验的服务名称',
    schedule_type VARCHAR(16) NOT NULL DEFAULT 'ONCE' COMMENT 'ONCE/CRON',
    cron_expression VARCHAR(128) NULL COMMENT 'Cron表达式',
    status VARCHAR(24) NOT NULL DEFAULT 'CREATED'
        COMMENT 'CREATED/PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED',
    created_by BIGINT UNSIGNED NOT NULL COMMENT '创建人',
    started_at DATETIME(3) NULL COMMENT '开始时间',
    finished_at DATETIME(3) NULL COMMENT '结束时间',
    timeout_seconds INT UNSIGNED NOT NULL DEFAULT 300 COMMENT '超时时间，单位：秒',
    confirmation_required TINYINT NOT NULL DEFAULT 0 COMMENT '是否需要二次确认',
    confirmed_by BIGINT UNSIGNED NULL COMMENT '确认人',
    confirmed_at DATETIME(3) NULL COMMENT '确认时间',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_ops_task_creator_time (created_by, created_at),
    KEY idx_ops_task_status (status),
    KEY idx_ops_task_schedule (schedule_type, status),
    CONSTRAINT fk_ops_task_created_by
        FOREIGN KEY (created_by) REFERENCES sys_user(id),
    CONSTRAINT fk_ops_task_confirmed_by
        FOREIGN KEY (confirmed_by) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='运维任务表';

CREATE TABLE ops_task_target (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务目标ID',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '目标服务器ID',
    target_status VARCHAR(24) NOT NULL DEFAULT 'PENDING'
        COMMENT 'PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_task_target (task_id, server_id),
    KEY idx_ops_task_target_server_id (server_id),
    KEY idx_ops_task_target_status (target_status),
    CONSTRAINT fk_ops_task_target_task
        FOREIGN KEY (task_id) REFERENCES ops_task(id),
    CONSTRAINT fk_ops_task_target_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='任务目标服务器表';

CREATE TABLE ops_task_execution (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务执行记录ID',
    task_id BIGINT UNSIGNED NOT NULL COMMENT '任务ID',
    target_id BIGINT UNSIGNED NOT NULL COMMENT '任务目标ID',
    server_id BIGINT UNSIGNED NOT NULL COMMENT '服务器ID',
    status VARCHAR(24) NOT NULL DEFAULT 'PENDING'
        COMMENT 'PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED',
    exit_code INT NULL COMMENT '进程退出码',
    result_text MEDIUMTEXT NULL COMMENT '执行结果',
    error_message TEXT NULL COMMENT '错误信息',
    started_at DATETIME(3) NULL COMMENT '开始时间',
    finished_at DATETIME(3) NULL COMMENT '结束时间',
    duration_ms BIGINT UNSIGNED NULL COMMENT '执行耗时，单位：毫秒',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_ops_task_execution_target (task_id, target_id),
    KEY idx_ops_task_execution_task_status (task_id, status),
    KEY idx_ops_task_execution_server_time (server_id, created_at),
    CONSTRAINT fk_ops_task_execution_task
        FOREIGN KEY (task_id) REFERENCES ops_task(id),
    CONSTRAINT fk_ops_task_execution_target
        FOREIGN KEY (target_id) REFERENCES ops_task_target(id),
    CONSTRAINT fk_ops_task_execution_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='任务执行记录表';

CREATE TABLE ops_task_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务日志ID',
    execution_id BIGINT UNSIGNED NOT NULL COMMENT '任务执行记录ID',
    log_level VARCHAR(16) NOT NULL DEFAULT 'INFO' COMMENT 'DEBUG/INFO/WARN/ERROR',
    log_content MEDIUMTEXT NOT NULL COMMENT '日志内容',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_ops_task_log_execution_time (execution_id, created_at),
    CONSTRAINT fk_ops_task_log_execution
        FOREIGN KEY (execution_id) REFERENCES ops_task_execution(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='任务执行日志表';

-- ============================================================
-- 六、登录与操作审计
-- ============================================================

CREATE TABLE sys_login_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '登录日志ID',
    user_id BIGINT UNSIGNED NULL COMMENT '用户ID，登录失败时可为空',
    username VARCHAR(64) NOT NULL COMMENT '登录用户名',
    login_ip VARCHAR(64) NULL COMMENT '登录IP',
    user_agent VARCHAR(500) NULL COMMENT '浏览器User-Agent',
    login_status VARCHAR(16) NOT NULL COMMENT 'SUCCESS/FAILED/LOCKED',
    failure_reason VARCHAR(255) NULL COMMENT '失败原因',
    request_id VARCHAR(64) NULL COMMENT '请求ID',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_sys_login_log_user_time (user_id, created_at),
    KEY idx_sys_login_log_username_time (username, created_at),
    KEY idx_sys_login_log_status_time (login_status, created_at),
    CONSTRAINT fk_sys_login_log_user
        FOREIGN KEY (user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='用户登录日志表';

CREATE TABLE sys_operation_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '操作日志ID',
    user_id BIGINT UNSIGNED NULL COMMENT '操作用户ID',
    username VARCHAR(64) NULL COMMENT '操作用户名快照',
    module VARCHAR(64) NOT NULL COMMENT '操作模块',
    operation VARCHAR(64) NOT NULL COMMENT '操作类型',
    http_method VARCHAR(16) NULL COMMENT 'HTTP方法',
    request_path VARCHAR(255) NULL COMMENT '请求路径',
    target_type VARCHAR(32) NULL COMMENT '目标类型',
    target_id BIGINT UNSIGNED NULL COMMENT '目标ID',
    server_id BIGINT UNSIGNED NULL COMMENT '目标服务器ID',
    request_ip VARCHAR(64) NULL COMMENT '请求IP',
    request_id VARCHAR(64) NULL COMMENT '请求ID',
    request_params JSON NULL COMMENT '请求参数，禁止记录密码和Token',
    result_status VARCHAR(24) NOT NULL COMMENT 'SUCCESS/FAILED',
    error_message TEXT NULL COMMENT '错误信息',
    duration_ms BIGINT UNSIGNED NULL COMMENT '请求耗时，单位：毫秒',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_sys_operation_log_user_time (user_id, created_at),
    KEY idx_sys_operation_log_server_time (server_id, created_at),
    KEY idx_sys_operation_log_module_time (module, created_at),
    KEY idx_sys_operation_log_status_time (result_status, created_at),
    KEY idx_sys_operation_log_created_at (created_at),
    CONSTRAINT fk_sys_operation_log_user
        FOREIGN KEY (user_id) REFERENCES sys_user(id),
    CONSTRAINT fk_sys_operation_log_server
        FOREIGN KEY (server_id) REFERENCES ops_server(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='系统操作审计日志表';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 七、可选初始化数据
-- 不在此处创建默认管理员，避免出现固定弱密码。
-- 建议由初始化程序生成密码哈希后插入 sys_user。
-- ============================================================

-- 示例：
-- INSERT INTO sys_role (role_code, role_name, description)
-- VALUES
-- ('SYSTEM_ADMIN', '系统管理员', '拥有系统全部管理权限'),
-- ('OPS_ENGINEER', '运维人员', '负责服务器监控、告警和任务操作'),
-- ('NORMAL_USER', '普通用户', '查看授权服务器和监控数据');

-- ============================================================
-- 八、常用查询示例
-- ============================================================

-- 查询服务器最近一小时监控数据：
-- SELECT *
-- FROM monitor_server_metric
-- WHERE server_id = ?
--   AND collected_at >= UTC_TIMESTAMP(3) - INTERVAL 1 HOUR
-- ORDER BY collected_at ASC;

-- 查询当前活动告警：
-- SELECT *
-- FROM alert_event
-- WHERE is_active = 1
-- ORDER BY created_at DESC;

-- 根据心跳时间刷新Agent状态的示例逻辑：
-- UPDATE ops_server
-- SET agent_status = CASE
--     WHEN last_heartbeat_at >= UTC_TIMESTAMP(3) - INTERVAL 30 SECOND THEN 'ONLINE'
--     WHEN last_heartbeat_at >= UTC_TIMESTAMP(3) - INTERVAL 90 SECOND THEN 'WARNING'
--     ELSE 'OFFLINE'
-- END
-- WHERE status = 1 AND deleted_at IS NULL;
