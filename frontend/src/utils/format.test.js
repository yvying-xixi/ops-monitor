import { describe, expect, it } from 'vitest'

import { formatBytes, formatUptime, orDash } from './format'

describe('formatBytes', () => {
  it('formats zero and nullish values', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(null)).toBe('-')
    expect(formatBytes(undefined)).toBe('-')
  })

  it('formats byte sizes', () => {
    expect(formatBytes(1024)).toBe('1 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(1024 * 1024)).toBe('1 MB')
  })
})

describe('formatUptime', () => {
  it('handles nullish values', () => {
    expect(formatUptime(null)).toBe('-')
  })

  it('formats minutes / hours / days', () => {
    expect(formatUptime(90)).toBe('1分钟')
    expect(formatUptime(3700)).toBe('1小时 1分')
    expect(formatUptime(90000)).toBe('1天 1小时')
  })
})

describe('orDash', () => {
  it('falls back for nullish values', () => {
    expect(orDash(null)).toBe('-')
    expect(orDash(undefined)).toBe('-')
    expect(orDash('value')).toBe('value')
  })
})
