/** 自动化任务接口。 */
import request from '../utils/request'

export function listTasksApi(params) {
  return request.get('/tasks', { params })
}

export function getTaskApi(id) {
  return request.get(`/tasks/${id}`)
}

export function createTaskApi(data) {
  return request.post('/tasks', data)
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
