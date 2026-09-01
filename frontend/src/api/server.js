/** 服务器管理接口。 */
import request from '../utils/request'

export function listServersApi(params) {
  return request.get('/servers', { params })
}

export function createServerApi(data) {
  return request.post('/servers', data)
}

export function getServerApi(id) {
  return request.get(`/servers/${id}`)
}

export function generateAgentTokenApi(id, tokenName) {
  return request.post(`/servers/${id}/agent-token`, null, {
    params: tokenName ? { token_name: tokenName } : {},
  })
}
