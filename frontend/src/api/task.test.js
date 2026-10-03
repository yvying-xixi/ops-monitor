import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../utils/request', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import request from '../utils/request'

import { createTaskApi } from './task'

describe('createTaskApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends an Idempotency-Key header', async () => {
    request.post.mockResolvedValue({ id: 1 })

    await createTaskApi({ task_name: 't', task_type: 'SERVICE_CHECK' })

    const [url, data, config] = request.post.mock.calls[0]
    expect(url).toBe('/tasks')
    expect(data).toEqual({ task_name: 't', task_type: 'SERVICE_CHECK' })
    expect(config.headers['Idempotency-Key']).toBeTruthy()
  })
})
