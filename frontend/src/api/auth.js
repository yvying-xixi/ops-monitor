/** 认证相关接口。 */
import request from '../utils/request'

export function loginApi(data) {
  return request.post('/auth/login', data)
}

export function getMeApi() {
  return request.get('/auth/me')
}
