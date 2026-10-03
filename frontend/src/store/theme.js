/** 主题状态管理（浅色 / 深色 / 跟随系统，持久化到 localStorage）。 */
import { defineStore } from 'pinia'

const THEME_KEY = 'ops_monitor_theme'
const MODES = ['light', 'dark', 'system']

const media = window.matchMedia('(prefers-color-scheme: dark)')

function resolveDark(mode) {
  if (mode === 'dark') return true
  if (mode === 'light') return false
  return media.matches
}

export const useThemeStore = defineStore('theme', {
  state: () => {
    const stored = localStorage.getItem(THEME_KEY)
    return {
      mode: MODES.includes(stored) ? stored : 'system',
    }
  },
  getters: {
    isDark: (state) => resolveDark(state.mode),
  },
  actions: {
    /** 将当前主题应用到 <html>（Element Plus dark 主题依赖 html.dark）。 */
    apply() {
      const dark = this.isDark
      document.documentElement.classList.toggle('dark', dark)
      document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
    },
    setMode(mode) {
      this.mode = MODES.includes(mode) ? mode : 'system'
      localStorage.setItem(THEME_KEY, this.mode)
      this.apply()
    },
    toggle() {
      this.setMode(this.isDark ? 'light' : 'dark')
    },
    /** 监听系统主题变化（仅在 system 模式下响应）。 */
    init() {
      this.apply()
      media.addEventListener('change', () => {
        if (this.mode === 'system') this.apply()
      })
    },
  },
})
