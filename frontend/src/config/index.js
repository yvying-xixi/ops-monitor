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

/** 角色编码常量 */
export const ROLE = {
  SYSTEM_ADMIN: 'SYSTEM_ADMIN',
  OPS_ENGINEER: 'OPS_ENGINEER',
  NORMAL_USER: 'NORMAL_USER',
}
