/** 全局配置常量。 */

export const BASE_URL = '/api/v1'

/** 指标时间范围选项 */
export const TIME_RANGES = [
  { value: '1h', label: '最近 1 小时' },
  { value: '6h', label: '最近 6 小时' },
  { value: '24h', label: '最近 24 小时' },
  { value: '7d', label: '最近 7 天' },
]

/** Agent 状态标签配置 */
export const AGENT_STATUS_MAP = {
  ONLINE: { type: 'success', label: '在线' },
  WARNING: { type: 'warning', label: '警告' },
  OFFLINE: { type: 'danger', label: '离线' },
  UNKNOWN: { type: 'info', label: '未知' },
}

/** 告警级别配置 */
export const ALERT_SEVERITY_MAP = {
  WARNING: { type: 'warning', label: '警告' },
  CRITICAL: { type: 'danger', label: '严重' },
}

/** 告警状态配置 */
export const ALERT_STATUS_MAP = {
  PENDING: { type: 'info', label: '待确认' },
  FIRING: { type: 'danger', label: '触发中' },
  ACKNOWLEDGED: { type: 'warning', label: '已确认' },
  RESOLVED: { type: 'success', label: '已恢复' },
}

/** 告警指标类型选项 */
export const ALERT_METRIC_TYPES = ['CPU', 'MEMORY', 'DISK', 'LOAD', 'AGENT']

/** 告警操作符选项 */
export const ALERT_OPERATORS = ['GT', 'GTE', 'LT', 'LTE', 'EQ']

/** 服务运行状态标签 */
export const SERVICE_STATUS_MAP = {
  RUNNING: { type: 'success', label: '运行中' },
  STOPPED: { type: 'info', label: '已停止' },
  FAILED: { type: 'danger', label: '异常' },
  UNKNOWN: { type: 'info', label: '未知' },
}

/** 任务状态标签 */
export const TASK_STATUS_MAP = {
  CREATED: { type: 'info', label: '待确认' },
  PENDING: { type: 'warning', label: '等待执行' },
  RUNNING: { type: 'primary', label: '执行中' },
  SUCCESS: { type: 'success', label: '成功' },
  FAILED: { type: 'danger', label: '失败' },
  TIMEOUT: { type: 'danger', label: '超时' },
  CANCELLED: { type: 'info', label: '已取消' },
}

/** 执行状态标签 */
export const EXEC_STATUS_MAP = TASK_STATUS_MAP

/** 角色编码常量 */
export const ROLE = {
  SYSTEM_ADMIN: 'SYSTEM_ADMIN',
  OPS_ENGINEER: 'OPS_ENGINEER',
  NORMAL_USER: 'NORMAL_USER',
}
