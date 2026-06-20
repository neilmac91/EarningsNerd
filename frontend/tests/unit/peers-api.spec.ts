import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
vi.mock('@/lib/api/client', () => ({
  default: { get: (...args: unknown[]) => get(...args) },
  ApiError: class ApiError extends Error {},
}))

import { getPeers } from '@/features/peers/api/peers-api'

describe('getPeers', () => {
  beforeEach(() => get.mockReset())

  it('calls the peers endpoint with the metric param and returns data', async () => {
    const payload = { ticker: 'AAPL', company_name: 'Apple Inc.', sic: '3571', concept: 'revenue', unit: 'USD', peer_count: 0, subject: {}, peers: [] }
    get.mockResolvedValue({ data: payload })

    const res = await getPeers('aapl', 'revenue')

    expect(get).toHaveBeenCalledWith('/api/companies/aapl/peers', { params: { metric: 'revenue' } })
    expect(res).toEqual(payload)
  })

  it('defaults the metric to revenue', async () => {
    get.mockResolvedValue({ data: {} })
    await getPeers('MSFT')
    expect(get).toHaveBeenCalledWith('/api/companies/MSFT/peers', { params: { metric: 'revenue' } })
  })
})
