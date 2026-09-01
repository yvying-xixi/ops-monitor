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

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (to.path !== '/login' && !userStore.isLoggedIn) {
    return { path: '/login' }
  }
  if (to.path === '/login' && userStore.isLoggedIn) {
    return { path: '/dashboard' }
  }
  if (to.meta.roles && !userStore.hasRole(...to.meta.roles)) {
    return { path: '/dashboard' }
  }
  document.title = to.meta.title ? `${to.meta.title} · 运维监控平台` : '运维监控平台'
  return true
})

export default router
