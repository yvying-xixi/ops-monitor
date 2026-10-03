/** 网关抖动/重启时的可安全重试判断。 */

export const GATEWAY_STATUS = [502, 503, 504]

/**
 * 判断网关错误是否可安全重试。
 *
 * - GET 幂等，可直接重试；
 * - POST 仅在携带 `Idempotency-Key` 时重试（服务端据此去重，避免重复创建）。
 *
 * @param {{method?: string, headers?: object}} config axios 请求配置
 * @param {number} status 响应状态码
 * @returns {boolean}
 */
export function isRetryableGatewayError(config, status) {
  if (!GATEWAY_STATUS.includes(status)) return false
  const method = (config?.method || '').toLowerCase()
  if (method === 'get') return true
  if (method === 'post') {
    const headers = config?.headers || {}
    return Boolean(headers['Idempotency-Key'] || headers['idempotency-key'])
  }
  return false
}
