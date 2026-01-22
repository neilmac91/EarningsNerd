import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { generateSummaryStream } from '@/features/summaries/api/summaries-api'
import { stripInternalNotices } from '@/lib/stripInternalNotices'

declare global {
  // eslint-disable-next-line no-var
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
    expect(progressSpy).toHaveBeenCalledWith('fetching', 'Fetching filing document...')
    expect(chunkSpy).toHaveBeenCalledWith('Executive summary text')
    expect(completeSpy).toHaveBeenCalledWith(42)
    expect(errorSpy).not.toHaveBeenCalled()
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

