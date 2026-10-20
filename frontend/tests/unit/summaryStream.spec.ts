import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { generateSummaryStream } from '@/features/summaries/api/summaries-api'
import { stripInternalNotices } from '@/lib/stripInternalNotices'

declare global {
  var fetch: typeof fetch
}

describe('generateSummaryStream', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
    global.fetch = originalFetch
  })

  it('invokes SSE callbacks in order for streamed events', async () => {
    const encoder = new TextEncoder()
    const chunks = [
      encoder.encode('data: {"type":"progress","stage":"fetching","message":"Fetching filing document..."}\n\n'),
      encoder.encode('data: {"type":"chunk","content":"Executive summary text"}\n\n'),
      encoder.encode('data: {"type":"complete","summary_id":42}\n\n'),
    ]

    let readIndex = 0
    const reader = {
      read: vi.fn(async () => {
        if (readIndex < chunks.length) {
          return { value: chunks[readIndex++], done: false }
        }
        return { value: undefined, done: true }
      }),
    }

    const fetchMock = vi.fn(async () => ({
      ok: true,
      body: {
        getReader: () => reader,
      },
    }))

    global.fetch = fetchMock as unknown as typeof fetch

    const progressSpy = vi.fn()
    const chunkSpy = vi.fn()
    const completeSpy = vi.fn()
    const errorSpy = vi.fn()

    await generateSummaryStream(101, chunkSpy, progressSpy, completeSpy, errorSpy)
    vi.runAllTimers()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(progressSpy).toHaveBeenCalledWith('fetching', 'Fetching filing document...', expect.anything())
    expect(chunkSpy).toHaveBeenCalledWith('Executive summary text')
    expect(completeSpy).toHaveBeenCalledWith(42)
    expect(errorSpy).not.toHaveBeenCalled()
  })

  // L1 contract (F2): a terminal `partial` frame is terminal — it drives onComplete with the saved
  // summary_id (so the view refetches + renders the partial, badge and all) and NEVER trips onError.
  // A regression that drops `partial` handling would strand the poller/generating state, so pin it.
  it('treats a terminal partial frame as complete (onComplete, not onError)', async () => {
    const encoder = new TextEncoder()
    const chunks = [
      encoder.encode('data: {"type":"chunk","content":"Partial analysis text"}\n\n'),
      encoder.encode('data: {"type":"partial","message":"Some sections may not have loaded fully.","summary_id":77}\n\n'),
    ]

    let readIndex = 0
    const reader = {
      read: vi.fn(async () => {
        if (readIndex < chunks.length) {
          return { value: chunks[readIndex++], done: false }
        }
        return { value: undefined, done: true }
      }),
    }

    const fetchMock = vi.fn(async () => ({
      ok: true,
      body: { getReader: () => reader },
    }))

    global.fetch = fetchMock as unknown as typeof fetch

    const chunkSpy = vi.fn()
    const progressSpy = vi.fn()
    const completeSpy = vi.fn()
    const errorSpy = vi.fn()

    await generateSummaryStream(202, chunkSpy, progressSpy, completeSpy, errorSpy)
    vi.runAllTimers()

    expect(chunkSpy).toHaveBeenCalledWith('Partial analysis text')
    expect(completeSpy).toHaveBeenCalledWith(77)
    expect(errorSpy).not.toHaveBeenCalled()
  })

  // Pro's fair-use pause (admission.py) holds until the month turns, so a second attempt would only repeat the
  // blocked request: the error surfaces at once (isNonRetryableStreamError; streamErrorCopy.spec.ts holds the
  // matcher to admission.py's sentence). An error frame a retry can help is attempted twice.
  it("makes no automatic second attempt at Pro's fair-use pause, and one at an error a retry can help", async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
    const attempts = async (message: string) => {
      const fetchMock = vi.fn(async () => new Response(`data: ${JSON.stringify({ type: 'error', message })}\n\n`))
      global.fetch = fetchMock as unknown as typeof fetch
      const errorSpy = vi.fn()
      const run = generateSummaryStream(303, vi.fn(), vi.fn(), vi.fn(), errorSpy).catch(() => undefined)
      await vi.runAllTimersAsync()
      await run
      return { requests: fetchMock.mock.calls.length, shown: errorSpy.mock.calls }
    }
    const pause =
      "We've temporarily paused new summary generation on your account due to unusually high recent volume. " +
      'Please try again later or contact support.'
    expect(await attempts(pause)).toEqual({ requests: 1, shown: [[pause]] })
    expect(await attempts('Provider unavailable')).toEqual({ requests: 2, shown: [['Provider unavailable']] })
  })
})

describe('stripInternalNotices', () => {
  it('removes leading internal disclaimers while preserving editorial content', () => {
    const input = `*Auto-generated from structured data because fallback.*

## Executive Summary
Polished investor-ready content.`

    const output = stripInternalNotices(input)
    expect(output).toBe(`## Executive Summary
Polished investor-ready content.`)
  })

  it('returns original content when no disclaimer is present', () => {
    const input = `## Executive Summary
Key highlights remain intact.`
    expect(stripInternalNotices(input)).toBe(input)
  })
})

