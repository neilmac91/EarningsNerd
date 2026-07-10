import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

// The raw SSE fetch bypasses the shared axios client, so it reuses the client's exact machinery
// (ensureRefreshed single-flight + hasActiveSession gate + clearSessionActive on failure). These
// pin that: an expired access cookie is recovered transparently (one refresh, one replay) instead
// of dead-ending a logged-in user on "Could not validate credentials" (review finding, #619/#620).
// ensureRefreshed() wraps refreshAccessToken, so mocking the latter still controls the outcome.
vi.mock('@/lib/api/refresh', () => ({
  refreshAccessToken: vi.fn(),
}))

import { generateSummaryStream } from '@/features/summaries/api/summaries-api'
import { refreshAccessToken } from '@/lib/api/refresh'
import { hasActiveSession } from '@/lib/api/session'

declare global {
  var fetch: typeof fetch
}

const okStream = () => {
  const encoder = new TextEncoder()
  const chunks = [encoder.encode('data: {"type":"complete","summary_id":7}\n\n')]
  let i = 0
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: vi.fn(async () =>
          i < chunks.length ? { value: chunks[i++], done: false } : { value: undefined, done: true },
        ),
      }),
    },
  }
}

const unauthorized = () => ({
  ok: false,
  status: 401,
  json: async () => ({ detail: 'Could not validate credentials' }),
})

describe('generateSummaryStream — expired-session silent refresh', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(refreshAccessToken).mockReset()
    // The refresh path gates on hasActiveSession() (a logged-in marker); mark it active so the
    // expired-cookie case is exercised rather than treated as a genuine guest 401.
    window.localStorage.setItem('en_session_active', '1')
  })
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
    global.fetch = originalFetch
    window.localStorage.clear()
  })

  it('refreshes once and replays on a 401, then streams to complete', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(unauthorized()) // expired access cookie
      .mockResolvedValueOnce(okStream()) // replay after refresh succeeds
    global.fetch = fetchMock as unknown as typeof fetch
    vi.mocked(refreshAccessToken).mockResolvedValue(undefined)

    const complete = vi.fn()
    const error = vi.fn()
    await generateSummaryStream(101, vi.fn(), vi.fn(), complete, error)
    vi.runAllTimers()

    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(complete).toHaveBeenCalledWith(7)
    expect(error).not.toHaveBeenCalled()
  })

  it('surfaces the auth error (no retry storm) when the refresh also fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue(unauthorized())
    global.fetch = fetchMock as unknown as typeof fetch
    vi.mocked(refreshAccessToken).mockRejectedValue(new Error('session gone'))

    const error = vi.fn()
    await expect(
      generateSummaryStream(101, vi.fn(), vi.fn(), vi.fn(), error),
    ).rejects.toThrow()
    vi.runAllTimers()

    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    // One initial POST + one refresh attempt; a 401 is non-retryable, so no outer-loop retry storm.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(error).toHaveBeenCalledWith(expect.stringMatching(/validate credentials/i))
    // A genuinely-gone session clears the advisory marker so the app stops treating it as live.
    expect(hasActiveSession()).toBe(false)
  })

  it('treats a network-level connect failure as retryable (outer loop retries, then surfaces it)', async () => {
    // A throw from the connect handshake (not a Response) must become a RETRYABLE result the outer
    // attempt loop re-tries — not propagate past it — mirroring the guarded streaming-read phase.
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    global.fetch = fetchMock as unknown as typeof fetch

    const error = vi.fn()
    // Attach the rejection handler synchronously (before advancing timers) so the reject that
    // fires during runAllTimersAsync isn't flagged as an unhandled rejection.
    let rejected = false
    const promise = generateSummaryStream(101, vi.fn(), vi.fn(), vi.fn(), error).catch(() => {
      rejected = true
    })
    await vi.runAllTimersAsync() // drive the inter-attempt backoff timer
    await promise

    expect(rejected).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(2) // initial attempt + one retry
    expect(refreshAccessToken).not.toHaveBeenCalled() // never got a 401 Response to refresh on
    expect(error).toHaveBeenCalled()
  })

  it('does NOT refresh when there is no active-session marker (a real guest 401)', async () => {
    window.localStorage.clear() // no en_session_active → hasActiveSession() false
    const fetchMock = vi.fn().mockResolvedValue(unauthorized())
    global.fetch = fetchMock as unknown as typeof fetch

    const error = vi.fn()
    await expect(
      generateSummaryStream(101, vi.fn(), vi.fn(), vi.fn(), error),
    ).rejects.toThrow()
    vi.runAllTimers()

    expect(refreshAccessToken).not.toHaveBeenCalled() // no pointless refresh for a guest
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
