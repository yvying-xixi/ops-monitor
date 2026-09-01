/** 用户管理接口。 */
import request from '../utils/request'

export function listUsersApi(params) {
  return request.get('/users', { params })
}

export function createUserApi(data) {
  return request.post('/users', data)
}

export function getUserApi(id) {
  return request.get(`/users/${id}`)
}

export function updateUserApi(id, data) {
  return request.put(`/users/${id}`, data)
}

export function deleteUserApi(id) {
  return request.delete(`/users/${id}`)
}
