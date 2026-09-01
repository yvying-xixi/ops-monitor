/** 告警中心接口。 */
import request from '../utils/request'

export function listAlertsApi(params) {
  return request.get('/alerts', { params })
}

export function getAlertApi(id) {
  return request.get(`/alerts/${id}`)
}

export function ackAlertApi(id) {
  return request.post(`/alerts/${id}/ack`)
}

export function resolveAlertApi(id) {
  return request.post(`/alerts/${id}/resolve`)
}

export function listRulesApi() {
  return request.get('/alerts/rules')
}

export function createRuleApi(data) {
  return request.post('/alerts/rules', data)
}

export function updateRuleApi(id, data) {
  return request.put(`/alerts/rules/${id}`, data)
}

export function deleteRuleApi(id) {
  return request.delete(`/alerts/rules/${id}`)
}
