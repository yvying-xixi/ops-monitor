/** 用户状态管理（Token 持久化 + 登录/登出 + 角色判断）。 */
import { defineStore } from 'pinia'
import { getMeApi, loginApi } from '../api/auth'

const TOKEN_KEY = 'ops_monitor_token'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    userInfo: null,
    roles: [],
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
    username: (state) => state.userInfo?.username || '',
    displayName: (state) => state.userInfo?.nickname || state.userInfo?.username || '',
    primaryRoleName: (state) => state.userInfo?.roles?.[0]?.role_name || '',
    isAdmin: (state) => state.roles.includes('SYSTEM_ADMIN'),
  },
  actions: {
    async login(username, password) {
      const data = await loginApi({ username, password })
      this.token = data.access_token
      localStorage.setItem(TOKEN_KEY, data.access_token)
      await this.fetchMe()
    },
    async fetchMe() {
      const me = await getMeApi()
      this.userInfo = me
      this.roles = (me.roles || []).map((r) => r.role_code)
    },
    hasRole(...codes) {
      return codes.some((code) => this.roles.includes(code))
    },
    logout() {
      this.token = ''
      this.userInfo = null
      this.roles = []
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
