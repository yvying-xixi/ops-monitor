import { describe, expect, it } from 'vitest'

import { isRetryableGatewayError } from './requestRetry'

describe('isRetryableGatewayError', () => {
  it('retries idempotent GET on gateway errors', () => {
    expect(isRetryableGatewayError({ method: 'get' }, 502)).toBe(true)
    expect(isRetryableGatewayError({ method: 'GET' }, 504)).toBe(true)
  })

  it('retries POST only when an Idempotency-Key is present', () => {
    expect(isRetryableGatewayError({ method: 'post' }, 503)).toBe(false)
    expect(
      isRetryableGatewayError({ method: 'post', headers: { 'Idempotency-Key': 'k' } }, 503)
    ).toBe(true)
    expect(
      isRetryableGatewayError({ method: 'post', headers: { 'idempotency-key': 'k' } }, 503)
    ).toBe(true)
  })

  it('does not retry non-gateway status or other methods', () => {
    expect(isRetryableGatewayError({ method: 'get' }, 500)).toBe(false)
    expect(isRetryableGatewayError({ method: 'delete' }, 502)).toBe(false)
    expect(isRetryableGatewayError({ method: 'post', headers: {} }, 200)).toBe(false)
  })
})
