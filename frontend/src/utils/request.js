/** axios 实例与统一拦截器。 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { BASE_URL } from '../config'
import { useUserStore } from '../store/user'
import router from '../router'
import { GATEWAY_STATUS, isRetryableGatewayError } from './requestRetry'

const MAX_RETRY = 2

const request = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

/** 剔除空查询参数（''、null、undefined），避免后端整型/枚举校验失败。 */
function cleanParams(params) {
  if (!params || typeof params !== 'object') return params
  const cleaned = { ...params }
  Object.keys(cleaned).forEach((key) => {
    const value = cleaned[key]
    if (value === '' || value === null || value === undefined) {
      delete cleaned[key]
    }
  })
  return cleaned
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 网关抖动/网络错误映射为友好文案，其余保留后端 message。 */
function errorMessage(error) {
  if (GATEWAY_STATUS.includes(error.response?.status)) {
    return '服务暂未就绪，请稍后重试'
  }
  return error.response?.data?.message || error.message || '网络错误'
}

// 请求拦截：注入 Token 并清理空查询参数
request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  config.params = cleanParams(config.params)
  return config
})

// 响应拦截：统一解包 data，处理错误
request.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res.data
  },
  async (error) => {
    const status = error.response?.status
    const config = error.config || {}

    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      if (router.currentRoute.value.path !== '/login') {
        router.push('/login')
      }
    }

    // 网关抖动（后端冷启动/重启）：GET 或带幂等键的 POST 退避重试
    if (isRetryableGatewayError(config, status) && (config.__retryCount || 0) < MAX_RETRY) {
      config.__retryCount = (config.__retryCount || 0) + 1
      await sleep(500 * config.__retryCount)
      return request(config)
    }

    ElMessage.error(errorMessage(error))
    return Promise.reject(error)
  },
)

export default request
