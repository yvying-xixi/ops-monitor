/** axios 实例与统一拦截器。 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { BASE_URL } from '../config'
import { useUserStore } from '../store/user'
import router from '../router'

const request = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

// 请求拦截：注入 Token
request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
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
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.message || error.message || '网络错误'
    if (status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      if (router.currentRoute.value.path !== '/login') {
        router.push('/login')
      }
    }
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default request
