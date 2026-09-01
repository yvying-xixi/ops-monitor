/** 角色接口。 */
import request from '../utils/request'

export function listRolesApi() {
  return request.get('/roles')
}
