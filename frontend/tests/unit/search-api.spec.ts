import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
vi.mock('@/lib/api/client', () => ({
  default: { get: (...args: unknown[]) => get(...args) },
  ApiError: class ApiError extends Error {},
}))

import { searchFullText } from '@/features/search/api/search-api'

describe('searchFullText', () => {
  beforeEach(() => get.mockReset())

  it('calls the EFTS endpoint with the given params and returns data', async () => {
    const payload = { query: 'going concern', total: 2, count: 1, hits: [] }
    get.mockResolvedValue({ data: payload })

    const res = await searchFullText({ q: 'going concern', forms: '10-K' })

    expect(get).toHaveBeenCalledWith('/api/search/full-text', {
      params: { q: 'going concern', forms: '10-K' },
    })
    expect(res).toEqual(payload)
  })

  it('passes only the params provided by the caller', async () => {
    get.mockResolvedValue({ data: { query: 'x', total: 0, count: 0, hits: [] } })

    await searchFullText({ q: 'x' })

    expect(get).toHaveBeenCalledWith('/api/search/full-text', { params: { q: 'x' } })
  })
})
