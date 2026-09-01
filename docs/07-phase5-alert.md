# 阶段五 · 告警中心

> 对应总体规划「五、告警管理」：阈值规则、WARNING/CRITICAL 分级、事件确认与恢复。
> 文档固化告警引擎设计、默认规则与接口约定。

## 一、告警引擎

**定时扫描 + DB 状态机持久化**：APScheduler 每 `ALERT_EVALUATE_INTERVAL_SECONDS`（默认 10s）执行一轮评估。

```
读取启用规则 × 启用服务器的最新指标/心跳
→ 未超阈值且存在活动告警 → RESOLVED
→ 超阈值无活动告警 → 创建 PENDING（first_fired_at=now）
→ PENDING 且持续 ≥ duration_seconds → 升级 FIRING
→ 每次状态变化写 alert_event_log
```

### 状态机

```
PENDING → FIRING → ACKNOWLEDGED → RESOLVED
```

- **去重**：`alert_key = {rule_id}:{server_id}:{metric_type}` + 数据库生成列 `is_active`
  唯一键，保证同一告警仅一条活动记录；恢复后 `is_active=NULL`，可再次触发。
- **ACKNOWLEDGED 保持活动**：确认后引擎仍跟踪，指标恢复时才解除。

## 二、规则语义

| metric_type | 取值 | 阈值语义 |
| --- | --- | --- |
| CPU / MEMORY / DISK | `monitor_server_metric` 最新值 | `value OP threshold` |
| LOAD | `load_1m` | threshold 视为 **cpu_cores 倍数**（如 1.0 / 2.0） |
| AGENT | `server.last_heartbeat_at` | value = 距当前秒数，`> threshold`（90s/180s） |

- operator：GT/GTE/LT/LTE/EQ（默认 GT）
- duration_seconds：PENDING→FIRING 所需持续异常时长
- recovery_threshold：低于即恢复；为空则回到阈值以下恢复
- 作用域：全局规则，作用于所有启用服务器

## 三、默认规则（启动幂等种子）

| 规则 | 指标 | 级别 | 阈值 | 持续 |
| --- | --- | --- | --- | --- |
| CPU 使用率过高 / 严重过高 | CPU | WARNING/CRITICAL | 80 / 95 | 300s / 120s |
| 内存使用率过高 / 严重过高 | MEMORY | WARNING/CRITICAL | 80 / 95 | 300s / 120s |
| 磁盘使用率过高 / 严重过高 | DISK | WARNING/CRITICAL | 85 / 95 | 300s / 120s |
| 负载过高 / 严重过高 | LOAD | WARNING/CRITICAL | 1.0 / 2.0（核数倍数） | 300s / 120s |
| Agent 心跳丢失 / 严重丢失 | AGENT | WARNING/CRITICAL | 90 / 180 | 0 |

## 四、接口

| 方法与路径 | 说明 | 权限 |
| --- | --- | --- |
| `GET /api/v1/alerts` | 事件分页（status/severity/server_id/active 筛选） | 登录 |
| `GET /api/v1/alerts/{id}` | 事件详情（含状态日志） | 登录 |
| `POST /api/v1/alerts/{id}/ack` | 确认告警 | SYSTEM_ADMIN/OPS_ENGINEER |
| `POST /api/v1/alerts/{id}/resolve` | 恢复告警 | SYSTEM_ADMIN/OPS_ENGINEER |
| `GET /api/v1/alerts/rules` | 规则列表 | 登录 |
| `POST /api/v1/alerts/rules` | 创建规则 | SYSTEM_ADMIN |
| `PUT /api/v1/alerts/rules/{id}` | 更新规则 | SYSTEM_ADMIN |
| `DELETE /api/v1/alerts/rules/{id}` | 删除规则 | SYSTEM_ADMIN |

> 路由顺序：`/alerts/rules` 声明在 `/alerts/{event_id}` 之前，避免被路径参数捕获。

## 五、前端

- `views/alert/index.vue`：告警事件列表（级别/状态/类型筛选、确认/恢复、详情时间线）+ 规则管理 tab
- Dashboard「实时告警」卡片：`active_alerts` 计数，点击跳告警中心
- 确认/恢复按钮按角色（SYSTEM_ADMIN/OPS_ENGINEER）显示

## 六、说明

- 通知渠道（短信/微信/钉钉）按需求边界不包含，仅事件管理。
- SERVICE/CONTAINER 规则本期不评估，随阶段六服务管理接入。
