import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { askFilingStream, type CopilotHandlers } from '@/features/filings/api/copilot-api'

// A reader that yields the given encoded chunks once, then signals done — mirrors the shape of
// response.body.getReader() the SSE consumer expects.
function bodyFrom(chunks: Uint8Array[]) {
  let i = 0
  return {
    getReader: () => ({
      read: vi.fn(async () => {
        if (i < chunks.length) return { value: chunks[i++], done: false }
        return { value: undefined, done: true }
      }),
    }),
  }
}

function handlers(overrides: Partial<CopilotHandlers> = {}): CopilotHandlers {
  return {
    onToken: vi.fn(),
    onComplete: vi.fn(),
    onError: vi.fn(),
    onNotDisclosed: vi.fn(),
    ...overrides,
  }
}

const enc = new TextEncoder()
const sse = (obj: unknown) => enc.encode(`data: ${JSON.stringify(obj)}\n`)

describe('askFilingStream token coalescing', () => {
  const originalFetch = global.fetch
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
    global.fetch = originalFetch
  })

  it('coalesces tokens that arrive within one frame into a single onToken at stream end', async () => {
    const chunks = [
      sse({ type: 'token', text: 'Rev' }),
      sse({ type: 'token', text: 'enue ' }),
      sse({ type: 'token', text: 'grew' }),
    ]
    global.fetch = vi.fn(async () => ({ ok: true, body: bodyFrom(chunks) })) as unknown as typeof fetch

    const h = handlers()
    await askFilingStream(1, 'q', [], h)
    vi.runAllTimers()

    // All three tokens were buffered before any frame boundary, then flushed once on graceful end.
    expect(h.onToken).toHaveBeenCalledTimes(1)
    expect(h.onToken).toHaveBeenCalledWith('Revenue grew')
    expect(h.onError).not.toHaveBeenCalled()
  })

  it('lets the complete event deliver the authoritative answer (buffered tokens superseded)', async () => {
    const chunks = [
      sse({ type: 'token', text: 'partial…' }),
      sse({
        type: 'complete',
        answer: 'Revenue grew 8%.',
        citations: [],
        grounded: 0,
        kind: 'answer',
        followups: [],
      }),
    ]
    global.fetch = vi.fn(async () => ({ ok: true, body: bodyFrom(chunks) })) as unknown as typeof fetch

    const h = handlers()
    await askFilingStream(1, 'q', [], h)
    vi.runAllTimers()

    // The buffered token never displaced the completion: complete fires with the full answer, and the
    // superseded buffer is discarded rather than flashed before the overwrite.
    expect(h.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({ answer: 'Revenue grew 8%.' }),
    )
    expect(h.onToken).not.toHaveBeenCalled()
  })

  it('reports onError (and does not throw) when a token handler throws during delivery', async () => {
    const chunks = [sse({ type: 'token', text: 'Rev' }), sse({ type: 'token', text: 'enue' })]
    global.fetch = vi.fn(async () => ({ ok: true, body: bodyFrom(chunks) })) as unknown as typeof fetch

    const onToken = vi.fn(() => {
      throw new Error('render blew up')
    })
    const onError = vi.fn()

    // deliverBuffer runs the handler outside the main try/catch (it can fire from a rAF). A throw
    // must be contained: surfaced via onError, never an unhandled rejection.
    await askFilingStream(1, 'q', [], handlers({ onToken, onError }))
    vi.runAllTimers()

    expect(onError).toHaveBeenCalledWith('render blew up')
  })

  it('discards buffered tokens on a not_disclosed completion', async () => {
    const chunks = [
      sse({ type: 'token', text: 'looking…' }),
      sse({ type: 'not_disclosed', answer: 'Not disclosed in this filing.' }),
    ]
    global.fetch = vi.fn(async () => ({ ok: true, body: bodyFrom(chunks) })) as unknown as typeof fetch

    const h = handlers()
    await askFilingStream(1, 'q', [], h)
    vi.runAllTimers()

    expect(h.onNotDisclosed).toHaveBeenCalledWith('Not disclosed in this filing.')
    expect(h.onToken).not.toHaveBeenCalled()
  })
})
