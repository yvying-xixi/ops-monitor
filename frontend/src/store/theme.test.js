import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useThemeStore } from './theme'

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
    setActivePinia(createPinia())
  })

  it('defaults to system mode', () => {
    const store = useThemeStore()
    expect(store.mode).toBe('system')
  })

  it('persists and applies dark mode', () => {
    const store = useThemeStore()
    store.setMode('dark')

    expect(store.mode).toBe('dark')
    expect(store.isDark).toBe(true)
    expect(localStorage.getItem('ops_monitor_theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('ignores invalid modes', () => {
    const store = useThemeStore()
    store.setMode('rainbow')
    expect(store.mode).toBe('system')
  })

  it('toggles between light and dark', () => {
    const store = useThemeStore()
    store.setMode('dark')
    store.toggle()
    expect(store.mode).toBe('light')
  })
})
