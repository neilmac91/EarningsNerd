import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
vi.mock('@/lib/api/client', () => ({
  default: { get: (...args: unknown[]) => get(...args) },
  ApiError: class ApiError extends Error {},
}))

import { getFilingFundamentals } from '@/features/fundamentals/api/fundamentals-api'

describe('getFilingFundamentals', () => {
  beforeEach(() => get.mockReset())

  it('calls the filing fundamentals endpoint and returns data', async () => {
    const payload = { ticker: 'AAPL', company_name: 'Apple Inc.', concepts: [] }
    get.mockResolvedValue({ data: payload })

    const res = await getFilingFundamentals(285)

    expect(get).toHaveBeenCalledWith('/api/filings/285/fundamentals')
    expect(res).toEqual(payload)
  })
})
