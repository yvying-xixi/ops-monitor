/** 自动化任务接口。 */
import request from '../utils/request'

/** 生成幂等键，避免网络重试造成重复创建任务。 */
function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function listTasksApi(params) {
  return request.get('/tasks', { params })
}

export function getTaskApi(id) {
  return request.get(`/tasks/${id}`)
}

export function createTaskApi(data) {
  return request.post('/tasks', data, {
    headers: { 'Idempotency-Key': newIdempotencyKey() },
  })
}

export function confirmTaskApi(id) {
  return request.post(`/tasks/${id}/confirm`)
}

export function cancelTaskApi(id) {
  return request.post(`/tasks/${id}/cancel`)
}

export function listServerServicesApi(serverId) {
  return request.get(`/servers/${serverId}/services`)
}

export function updateServiceWhitelistApi(serverId, serviceId, isWhitelisted) {
  return request.put(`/servers/${serverId}/services/${serviceId}/whitelist`, { is_whitelisted: isWhitelisted })
}
