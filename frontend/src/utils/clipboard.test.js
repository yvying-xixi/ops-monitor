import { afterEach, describe, expect, it, vi } from 'vitest'

import { copyText } from './clipboard'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('copyText', () => {
  it('returns false for empty input', async () => {
    expect(await copyText('')).toBe(false)
    expect(await copyText(null)).toBe(false)
  })

  it('uses the Clipboard API in a secure context', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })

    expect(await copyText('hello')).toBe(true)
    expect(writeText).toHaveBeenCalledWith('hello')
  })

  it('falls back to execCommand when Clipboard API is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
    const execCommand = vi.fn().mockReturnValue(true)
    document.execCommand = execCommand

    expect(await copyText('fallback')).toBe(true)
    expect(execCommand).toHaveBeenCalledWith('copy')
  })
})
