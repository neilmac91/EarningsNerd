import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const consent = vi.hoisted(() => ({ analytics: true }))
vi.mock('@/components/CookieConsent', () => ({ getCookiePreferences: () => consent }))
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn(async () => {}) }))
import { generateSummaryStream } from '@/features/summaries/api/summaries-api'

const complete = () => new Response('data: {"type":"complete","summary_id":7}\n\n')
const run = () => generateSummaryStream(101, vi.fn(), vi.fn(), vi.fn(), vi.fn())
const query = (url: string) => new URL(url, 'https://example.test').searchParams

describe('summary request correlation and capture-time consent', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    consent.analytics = true
    window.localStorage.clear()
  })
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  it('keeps one action ID across automatic retries and gives a later action a new ID', async () => {
    const requests: URLSearchParams[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      requests.push(query(url))
      if (requests.length === 1) throw new TypeError('connect failed')
      return complete()
    }))
    const first = run()
    await vi.runAllTimersAsync()
    await first
    await run()
    const ids = requests.map((q) => q.get('logical_request_id'))
    expect(ids[0]).toMatch(/^[0-9a-f-]{36}$/)
    expect(ids[1]).toBe(ids[0])
    expect(ids[2]).not.toBe(ids[0])
    expect(requests.map((q) => q.get('client_attempt'))).toEqual(['1', '2', '1'])
    expect(requests.map((q) => q.get('transport_attempt'))).toEqual(['1', '1', '1'])
    expect(requests.every((q) => q.get('analytics_consent') === 'true')).toBe(true)
    expect(requests.every((q) => !q.has('ph_id'))).toBe(true)
  })

  it('labels an auth replay separately while retaining the same client action and outer attempt', async () => {
    window.localStorage.setItem('en_session_active', '1')
    const requests: URLSearchParams[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      requests.push(query(url))
      return requests.length === 1 ? new Response('{}', { status: 401 }) : complete()
    }))
    await run()
    expect(requests).toHaveLength(2)
    expect(requests[1].get('logical_request_id')).toBe(requests[0].get('logical_request_id'))
    expect(requests.map((q) => q.get('client_attempt'))).toEqual(['1', '1'])
    expect(requests.map((q) => q.get('transport_attempt'))).toEqual(['1', '2'])
  })

  it.each(['initial', 'outer_retry', 'auth_replay'] as const)('omits analytics metadata after consent is absent at %s', async (where) => {
    if (where === 'initial') consent.analytics = false
    if (where === 'auth_replay') window.localStorage.setItem('en_session_active', '1')
    const requests: URLSearchParams[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      requests.push(query(url))
      if (requests.length === 1 && where !== 'initial') {
        consent.analytics = false
        if (where === 'auth_replay') return new Response('{}', { status: 401 })
        throw new TypeError('connect failed')
      }
      return complete()
    }))
    const pending = run()
    await vi.runAllTimersAsync()
    await pending
    const last = requests.at(-1)!
    for (const key of ['analytics_consent', 'logical_request_id', 'client_attempt', 'transport_attempt', 'ph_id']) {
      expect(last.has(key)).toBe(false)
    }
  })

  it('does not block generation when UUID support is unavailable', async () => {
    vi.stubGlobal('crypto', {})
    const fetch = vi.fn(async (_url: string) => complete())
    vi.stubGlobal('fetch', fetch)
    await run()
    expect(query(fetch.mock.calls[0][0] as string).has('logical_request_id')).toBe(false)
  })
})
