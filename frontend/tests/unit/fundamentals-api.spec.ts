import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
vi.mock('@/lib/api/client', () => ({
  default: { get: (...args: unknown[]) => get(...args) },
  ApiError: class ApiError extends Error {},
}))

import { getFundamentals } from '@/features/fundamentals/api/fundamentals-api'

describe('getFundamentals', () => {
  beforeEach(() => get.mockReset())

  it('calls the company fundamentals endpoint and returns data', async () => {
    const payload = { ticker: 'AAPL', company_name: 'Apple Inc.', concepts: [] }
    get.mockResolvedValue({ data: payload })

    const res = await getFundamentals('aapl')

    expect(get).toHaveBeenCalledWith('/api/companies/aapl/fundamentals')
    expect(res).toEqual(payload)
  })
})
