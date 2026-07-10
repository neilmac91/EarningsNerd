import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

// The raw SSE fetch bypasses the shared axios client, so it must replicate the client's silent
// 401 → /refresh → replay. These pin that: an expired access cookie is recovered transparently
// (one refresh, one replay) instead of dead-ending a logged-in user on "Could not validate
// credentials" with a Retry that re-sends the same expired cookie (review finding, #619/#620).
vi.mock('@/lib/api/refresh', () => ({
  refreshAccessToken: vi.fn(),
}))

import { generateSummaryStream } from '@/features/summaries/api/summaries-api'
import { refreshAccessToken } from '@/lib/api/refresh'

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
  })
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
    global.fetch = originalFetch
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
  })
})
