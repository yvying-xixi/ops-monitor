<script setup>
import { useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Monitor, Cpu, Bell, User, SwitchButton, Aim } from '@element-plus/icons-vue'
import { useUserStore } from '../store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menus = computed(() => {
  const items = [
    { index: '/dashboard', title: '监控总览', icon: Monitor },
    { index: '/servers', title: '服务器管理', icon: Cpu },
    { index: '/alerts', title: '告警中心', icon: Bell },
    { index: '/tasks', title: '任务中心', icon: Aim },
  ]
  if (userStore.isAdmin) {
    items.push({ index: '/system/users', title: '用户管理', icon: User })
  }
  return items
})

const activeMenu = computed(() => {
  if (route.path.startsWith('/servers/')) return '/servers'
  return route.path
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？退出后需重新登录才能继续使用。', '退出登录', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">运维监控平台</div>
      <el-menu :default-active="activeMenu" router background-color="#001529" text-color="#c0c4cc" active-text-color="#ffffff">
        <el-menu-item v-for="menu in menus" :key="menu.index" :index="menu.index">
          <el-icon><component :is="menu.icon" /></el-icon>
          <span>{{ menu.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-title">{{ route.meta.title || '' }}</div>
        <el-dropdown @command="handleLogout">
          <span class="user">
            <el-avatar :size="28" class="user-avatar">{{ userStore.displayName.charAt(0).toUpperCase() }}</el-avatar>
            <span class="user-name">{{ userStore.displayName }}</span>
            <el-tag v-if="userStore.primaryRoleName" size="small" type="info" effect="plain" class="user-role">
              {{ userStore.primaryRoleName }}
            </el-tag>
            <el-icon><SwitchButton /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background-color: #001529;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.aside :deep(.el-menu) {
  border-right: none;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #303133;
}
.user-avatar {
  background: #409eff;
  color: #fff;
  font-size: 14px;
}
.user-name {
  font-size: 14px;
}
.user-role {
  margin-left: 0;
}
.main {
  background-color: #f0f2f5;
}
</style>
