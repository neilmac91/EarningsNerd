import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getLegalReadiness } from '@/features/legal/api/legal-api'
import { legalReady } from './fixtures/legalReady'

const get = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api/client', () => ({ default: { get } }))
beforeEach(() => get.mockReset())

describe('readiness transport rejects ambiguous decisions', () => {
  it.each([
    null,
    { ...legalReady, collection_available: 'true' },
    { ...legalReady, checkout_available: undefined },
    { ...legalReady, marketing_available: null },
    { ...legalReady, terms_version: '' },
    { ...legalReady, eligibility_version: undefined },
    { ...legalReady, operator: undefined },
    { ...legalReady, operator: null },
    { ...legalReady, collection_available: false, checkout_available: true, operator: null },
    { ...legalReady, operator: { legal_name: 'Only a name' } },
  ])('refuses malformed readiness %#', async (data) => {
    get.mockResolvedValue({ data })
    await expect(getLegalReadiness()).rejects.toThrow('Availability could not be checked.')
  })

  it('uses the shared API client with cancellation and makes a new read on every call', async () => {
    get.mockResolvedValue({ data: legalReady })
    const signal = new AbortController().signal
    await expect(getLegalReadiness(signal)).resolves.toEqual(legalReady)
    await getLegalReadiness(signal)
    expect(get).toHaveBeenCalledTimes(2)
    expect(get).toHaveBeenLastCalledWith('/api/legal/readiness', { signal })
  })
})
