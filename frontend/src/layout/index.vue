<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  Monitor,
  Cpu,
  Bell,
  User,
  Aim,
  SwitchButton,
  Fold,
  Expand,
  Menu as MenuIcon,
  Sunny,
  Moon,
  Monitor as MonitorIcon,
} from '@element-plus/icons-vue'
import { useUserStore } from '../store/user'
import { useThemeStore } from '../store/theme'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const collapsed = ref(false)
const drawerVisible = ref(false)
const isMobile = ref(false)
const mq = window.matchMedia('(max-width: 1023px)')

function syncMobile() {
  isMobile.value = mq.matches
  if (!mq.matches) drawerVisible.value = false
}

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

const themeIcon = computed(() => {
  if (themeStore.mode === 'light') return Sunny
  if (themeStore.mode === 'dark') return Moon
  return MonitorIcon
})

const themeLabel = computed(
  () => ({ light: '浅色', dark: '深色', system: '跟随系统' })[themeStore.mode] || '跟随系统',
)

function toggleSidebar() {
  if (isMobile.value) {
    drawerVisible.value = true
  } else {
    collapsed.value = !collapsed.value
  }
}

function onMenuSelect() {
  if (isMobile.value) drawerVisible.value = false
}

function handleTheme(mode) {
  themeStore.setMode(mode)
}

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

onMounted(() => {
  syncMobile()
  mq.addEventListener('change', syncMobile)
})
onUnmounted(() => mq.removeEventListener('change', syncMobile))
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- 桌面侧栏 -->
    <aside
      v-if="!isMobile"
      class="flex shrink-0 flex-col bg-brand-700 text-white transition-[width] duration-200"
      :class="collapsed ? 'w-16' : 'w-56'"
    >
      <div class="flex h-14 shrink-0 items-center justify-center gap-2 px-2">
        <span class="text-base font-semibold tracking-wide">{{ collapsed ? '运维' : '运维监控平台' }}</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        :collapse="collapsed"
        :collapse-transition="false"
        background-color="#1f3b73"
        text-color="#c0c4cc"
        active-text-color="#ffffff"
        class="flex-1 overflow-y-auto border-r-0"
        @select="onMenuSelect"
      >
        <el-menu-item v-for="menu in menus" :key="menu.index" :index="menu.index" :title="menu.title">
          <el-icon><component :is="menu.icon" /></el-icon>
          <template #title>{{ menu.title }}</template>
        </el-menu-item>
      </el-menu>
    </aside>

    <!-- 小屏抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="220px"
      :with-header="false"
      class="layout-drawer"
    >
      <div class="flex h-14 items-center justify-center bg-brand-700 text-base font-semibold text-white">
        运维监控平台
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#1f3b73"
        text-color="#c0c4cc"
        active-text-color="#ffffff"
        class="border-r-0"
        @select="onMenuSelect"
      >
        <el-menu-item v-for="menu in menus" :key="menu.index" :index="menu.index">
          <el-icon><component :is="menu.icon" /></el-icon>
          <template #title>{{ menu.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <!-- 顶栏 -->
      <header
        class="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-3 border-b border-[var(--el-border-color-lighter)] bg-[var(--el-bg-color)] px-4"
      >
        <el-button text class="!p-2" @click="toggleSidebar">
          <el-icon :size="20">
            <component :is="isMobile ? MenuIcon : collapsed ? Expand : Fold" />
          </el-icon>
        </el-button>
        <div class="truncate text-base font-semibold">{{ route.meta.title || '' }}</div>
        <div class="flex-1"></div>

        <el-dropdown @command="handleTheme">
          <el-button text class="!p-2" :title="`主题：${themeLabel}`">
            <el-icon :size="18"><component :is="themeIcon" /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="light" :disabled="themeStore.mode === 'light'">浅色</el-dropdown-item>
              <el-dropdown-item command="dark" :disabled="themeStore.mode === 'dark'">深色</el-dropdown-item>
              <el-dropdown-item command="system" :disabled="themeStore.mode === 'system'">跟随系统</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-dropdown @command="handleLogout">
          <span class="user">
            <el-avatar :size="28" class="user-avatar">{{ userStore.displayName.charAt(0).toUpperCase() }}</el-avatar>
            <span class="user-name">{{ userStore.displayName }}</span>
            <el-tag v-if="userStore.primaryRoleName" size="small" type="info" effect="plain">
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
      </header>

      <main class="flex-1 overflow-auto bg-[var(--el-bg-color-page)] p-4">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--el-text-color-primary);
}
.user-avatar {
  background: var(--el-color-primary);
  color: #fff;
  font-size: 14px;
}
.user-name {
  font-size: 14px;
}
@media (max-width: 640px) {
  .user-name {
    display: none;
  }
}
</style>

<style>
/* 抽屉内容贴合边缘，去掉默认内边距 */
.layout-drawer .el-drawer__body {
  padding: 0;
}
</style>
