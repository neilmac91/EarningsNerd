import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * The filing page prints a failed run's reason on its "Generation interrupted" card. A backend sentence is
 * mapped where it is shown (features/summaries/lib/streamErrorCopy.ts, held to the Python by
 * streamErrorCopy.spec.ts); the stream client's and the hook's own fallbacks are printed as written, so
 * each is pinned here, path by path, and read in the product voice (filing/F17): a sentence, no em-dash,
 * no exclamation mark, no "Please", and never the transport's own text ("Failed to fetch", "Request
 * failed with status 500", an API URL). A 401 is never retried whatever its text; a 5xx, a dropped or
 * closed stream, a fetch that throws and the idle timeout are retried once, then shown.
 */

const getSummary = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: () => Promise.resolve() }))
vi.mock('@/features/summaries/api/summaries-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/summaries/api/summaries-api')>()),
  getSummary,
}))
import { generateSummaryStream } from '@/features/summaries/api/summaries-api'
import { useSummaryGeneration } from '@/features/summaries/hooks/useSummaryGeneration'
import { ApiError } from '@/lib/api/client'
import type { Filing } from '@/features/filings/api/filings-api'

const encoder = new TextEncoder()
const frame = (data: object) => `data: ${JSON.stringify(data)}\n\n`
const stream = (parts: string[], keepOpen = false) =>
  new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        parts.forEach((part) => controller.enqueue(encoder.encode(part)))
        if (!keepOpen) controller.close()
      },
    }),
  )

/** Runs one generation against `answer` (called per request) and returns what onError received. */
async function failureOf(answer: () => Promise<Response>) {
  const fetch = vi.fn(answer)
  vi.stubGlobal('fetch', fetch)
  const error = vi.fn()
  const done = generateSummaryStream(101, vi.fn(), vi.fn(), vi.fn(), error).catch(() => undefined)
  await vi.runAllTimersAsync()
  await done
  expect(error).toHaveBeenCalledOnce()
  return { shown: error.mock.calls[0][0] as string, requests: fetch.mock.calls.length }
}

/** What the card prints, read in the voice. */
function inTheVoice(sentence: string) {
  expect(sentence).toMatch(/^[A-Z].*\.$/)
  expect(sentence).not.toMatch(/—|!|\bplease\b/i)
  expect(sentence).not.toMatch(/failed to fetch|load failed|networkerror|status code|request failed|https?:/i)
}

describe('the summary stream client prints its own fallbacks in the voice', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    window.localStorage.clear()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it.each([
    [401, 'Log in again to generate this summary.', 1],
    [400, 'The summary could not start. Try again.', 1],
    [403, 'Your account does not have permission to generate this summary.', 1],
    [429, 'Too many summary requests just now. Try again shortly.', 1],
    [500, 'The server could not start the summary. Try again in a moment.', 2],
  ])('a %i with no detail of its own reads "%s"', async (status, sentence, requests) => {
    const result = await failureOf(async () => new Response(null, { status }))
    expect(result).toEqual({ shown: sentence, requests })
    inTheVoice(sentence)
  })

  it('a response with no body to read', async () => {
    const result = await failureOf(async () => ({ ok: true, status: 200, body: null }) as unknown as Response)
    expect(result).toEqual({ shown: 'The connection dropped before the summary started. Try again.', requests: 2 })
    inTheVoice(result.shown)
  })

  it('an invalid completion frame', async () => {
    const result = await failureOf(async () => stream([frame({ type: 'complete', summary_id: '42' })]))
    expect(result).toEqual({ shown: 'The summary ended with an invalid completion. Try again.', requests: 2 })
    inTheVoice(result.shown)
  })

  it('a stream that closes before its terminal frame', async () => {
    const result = await failureOf(async () => stream([]))
    expect(result).toEqual({ shown: 'The connection closed before the summary finished. Try again.', requests: 2 })
    inTheVoice(result.shown)
  })

  it.each(['Failed to fetch', 'Load failed', 'NetworkError when attempting to fetch resource.'])(
    'a fetch that throws the browser’s "%s"',
    async (text) => {
      const result = await failureOf(async () => {
        throw new TypeError(text)
      })
      expect(result).toEqual({ shown: 'The connection dropped before the summary finished. Try again.', requests: 2 })
      inTheVoice(result.shown)
      // The transport's own text still reaches the console, where it helps.
      expect(console.warn).toHaveBeenCalledWith(expect.stringContaining(text))
    },
  )

  it('a stream with no activity for the idle timeout', async () => {
    const result = await failureOf(async () => stream([], true))
    expect(result).toEqual({ shown: 'The summary timed out after 120 seconds without progress. Try again.', requests: 2 })
    inTheVoice(result.shown)
  })
})

describe('the summary hook prints its own fallbacks in the voice', () => {
  const filing = { id: 42, filing_type: '10-K', company: { id: 1, ticker: 'ACME', name: 'Acme Corp' } } as unknown as Filing
  const read = () =>
    renderHook(
      () => useSummaryGeneration({ filingId: filing.id, filing, isAuthenticated: false, isAuthResolved: true, entryPoint: 'test' }),
      {
        wrapper: ({ children }: { children: React.ReactNode }) => (
          <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
        ),
      },
    )
  afterEach(() => getSummary.mockReset())

  it('keeps the API client’s own status sentence off the card, and shows what the backend wrote', async () => {
    // The client's sentence for a dropped connection names the API's URL: transport text, not copy.
    getSummary.mockRejectedValue(new ApiError(0, 'Unable to connect to the server. Please ensure the backend API is running on http://localhost:8000'))
    const fallback = read()
    await waitFor(() => expect(fallback.result.current.activeErrorMessage).toBe('The summary could not load. Try again.'))
    inTheVoice(fallback.result.current.activeErrorMessage!)
    fallback.unmount()

    const written = Object.assign(new ApiError(500, 'Summary unavailable for this filing.'), { backendDetail: 'Summary unavailable for this filing.' })
    getSummary.mockRejectedValue(written)
    const backend = read()
    await waitFor(() => expect(backend.result.current.activeErrorMessage).toBe('Summary unavailable for this filing.'))
  })
})
