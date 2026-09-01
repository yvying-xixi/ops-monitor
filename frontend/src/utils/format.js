/** 通用工具函数。 */

/** 字节数格式化为可读大小 */
export function formatBytes(bytes, decimals = 2) {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${units[i]}`
}

/** 秒数格式化为可读时长 */
export function formatUptime(seconds) {
  if (seconds === null || seconds === undefined) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}天 ${hours}小时`
  if (hours > 0) return `${hours}小时 ${minutes}分`
  return `${minutes}分钟`
}

/** 时间格式化为本地时间字符串 */
export function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

/** 空值兜底 */
export function orDash(value) {
  return value === null || value === undefined ? '-' : value
}
