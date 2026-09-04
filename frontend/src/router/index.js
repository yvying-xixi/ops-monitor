/** 路由配置与全局守卫。 */
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../store/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/index.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: () => import('../layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/dashboard/index.vue'),
        meta: { title: '监控总览' },
      },
      {
        path: 'servers',
        name: 'Servers',
        component: () => import('../views/server/index.vue'),
        meta: { title: '服务器管理' },
      },
      {
        path: 'servers/:id',
        name: 'ServerDetail',
        component: () => import('../views/server/detail.vue'),
        meta: { title: '服务器详情' },
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: () => import('../views/alert/index.vue'),
        meta: { title: '告警中心' },
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('../views/task/index.vue'),
        meta: { title: '任务中心' },
      },
      {
        path: 'system/users',
        name: 'Users',
        component: () => import('../views/system/user.vue'),
        meta: { title: '用户管理', roles: ['SYSTEM_ADMIN'] },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 会话恢复标记：刷新后仅尝试一次拉取用户信息，避免导航期间重复请求
let restoreAttempted = false

router.beforeEach(async (to) => {
  const userStore = useUserStore()
  const needsAuth = to.path !== '/login'

  if (needsAuth && !userStore.isLoggedIn) {
    return { path: '/login' }
  }
  if (to.path === '/login' && userStore.isLoggedIn) {
    return { path: '/dashboard' }
  }

  // 启动/刷新后恢复用户信息与角色（页面刷新时 token 已持久化但 userInfo 为空）
  if (needsAuth && userStore.isLoggedIn && !userStore.userInfo && !restoreAttempted) {
    restoreAttempted = true
    try {
      await userStore.fetchMe()
    } catch (e) {
      // 401 已由拦截器登出并跳转；其余错误放行（角色受限页由服务端鉴权兜底）
    }
    if (!userStore.isLoggedIn) {
      return { path: '/login' }
    }
  }

  if (to.meta.roles && !userStore.hasRole(...to.meta.roles)) {
    return { path: '/dashboard' }
  }
  document.title = to.meta.title ? `${to.meta.title} · 运维监控平台` : '运维监控平台'
  return true
})

export default router
