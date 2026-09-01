/** 监控中心接口。 */
import request from '../utils/request'

export function getLatestMetricApi(serverId) {
  return request.get(`/servers/${serverId}/metrics/latest`)
}

export function getHistoryMetricApi(serverId, params) {
  return request.get(`/servers/${serverId}/metrics/history`, { params })
}

export function getSummaryMetricApi(serverId, timeRange) {
  return request.get(`/servers/${serverId}/metrics/summary`, {
    params: { range: timeRange },
  })
}

export function getServerAssetsApi(serverId) {
  return request.get(`/servers/${serverId}/assets`)
}

export function getDashboardOverviewApi() {
  return request.get('/dashboard/overview')
}
