/** 服务器只读发现接口。 */
import request from '../utils/request'

export function getDiscoveryConfigApi() {
  return request.get('/discovery/config')
}

export function scanNetworkApi(data) {
  return request.post('/discovery/scan', data)
}
