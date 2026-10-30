import React from 'react'
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Filing } from '@/features/filings/api/filings-api'

const mocks = vi.hoisted(() => ({ summary: vi.fn(), progress: vi.fn() }))
vi.mock('@/features/summaries/api/summaries-api', async (original) => ({
  ...await original<typeof import('@/features/summaries/api/summaries-api')>(),
  getSummary: mocks.summary,
  getSummaryProgress: mocks.progress,
}))
vi.mock('@/lib/analytics', () => ({ default: { paywallPromptShown: vi.fn() } }))
import { useSummaryGeneration } from '@/features/summaries/hooks/useSummaryGeneration'
import { generateSummaryStream, summaryRetryAfter, type Summary } from '@/features/summaries/api/summaries-api'
import StreamingSummaryDisplay from '@/app/filing/[id]/StreamingSummaryDisplay'

const filing = { id: 45003, filing_type: '10-Q', company: { ticker: 'REGN' } } as Filing
const READY: Summary = { id: 73, filing_id: filing.id, business_overview: 'A grounded completed summary.' }
const GENERIC = 'We could not generate this summary. Try again shortly.'
const LIMITED = 'Too many summary requests. Try again shortly.'
const frame = (data: object) => `data: ${JSON.stringify(data)}\n\n`
const errorStream = () => new Response(frame({ type: 'error', message: GENERIC, code: 'filing_source_unavailable' }))
const clients: QueryClient[] = []

function mount(initialSummary?: Summary | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(client)
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return renderHook(() => useSummaryGeneration({ filingId: filing.id, filing, isAuthenticated: true,
    isAuthResolved: true, entryPoint: 'email', initialSummary }), { wrapper })
}

beforeEach(() => {
  mocks.summary.mockReset().mockResolvedValue(null)
  mocks.progress.mockReset().mockResolvedValue({ stage: 'fetching', elapsedSeconds: 1 })
  vi.spyOn(console, 'info').mockImplementation(() => {})
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})
afterEach(() => {
  cleanup()
  clients.splice(0).forEach((client) => client.clear())
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('the fresh-filing recovery flow', () => {
  it('does not replay a source failure; a double Retry joins one ordinary action', async () => {
    const fetch = vi.fn(async () => errorStream())
    vi.stubGlobal('fetch', fetch)
    const view = mount()
    await waitFor(() => expect(view.result.current.generationError).toBe(GENERIC))
    expect(fetch).toHaveBeenCalledTimes(1)
    expect((fetch.mock.calls as unknown as Array<[string]>)[0][0]).not.toContain('retry_failed')
    await act(async () => { view.result.current.handleRetrySummary(); view.result.current.handleRetrySummary() })
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect((fetch.mock.calls as unknown as Array<[string]>)[1][0]).toContain('retry_failed=true')
    await waitFor(() => expect(view.result.current.isStreaming).toBe(false))
    for (const [url] of fetch.mock.calls as unknown as Array<[string]>) expect(url).not.toContain('force=true')
    for (let n = 0; n < 10; n++) view.rerender()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('honors the account cooldown and reads a result that arrives before Retry', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ detail: LIMITED, code: 'summary_rate_limited' }),
      { status: 429, headers: { 'Retry-After': '30', 'X-Correlation-ID': 'incident-request' } }))
    vi.stubGlobal('fetch', fetch)
    const view = mount()
    await waitFor(() => expect(view.result.current.retryAfterSeconds).toBe(30))
    expect(view.result.current.generationFailure).toMatchObject({ code: 'summary_rate_limited', requestId: 'incident-request' })
    await act(async () => { view.result.current.handleRetrySummary() })
    expect(fetch).toHaveBeenCalledTimes(1)
    mocks.summary.mockResolvedValue(READY)
    const later = Date.now() + 31_000
    vi.spyOn(Date, 'now').mockReturnValue(later)
    await act(async () => { view.result.current.handleRetrySummary() })
    await waitFor(() => expect(view.result.current.summary?.id).toBe(READY.id))
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('recovers a committed result after EOF before replaying generation', async () => {
    const fetch = vi.fn(async () => {
      mocks.summary.mockResolvedValue(READY)
      return new Response('')
    })
    vi.stubGlobal('fetch', fetch)
    const view = mount()
    await waitFor(() => expect(view.result.current.summary?.id).toBe(READY.id))
    expect(view.result.current.generationError).toBeNull()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('does not let an older query erase a result recovered by Retry', async () => {
    let release: (value: null) => void = () => {}
    mocks.summary.mockImplementationOnce(() => new Promise<null>((resolve) => { release = resolve }))
      .mockResolvedValue(READY)
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    const view = mount(null)
    await act(async () => { await view.result.current.handleGenerateSummary() })
    await waitFor(() => expect(view.result.current.summary?.id).toBe(READY.id))
    await act(async () => { release(null); await Promise.resolve() })
    expect(view.result.current.summary?.id).toBe(READY.id)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('surfaces a failed result read after a successful completion instead of spinning forever', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      mocks.summary.mockRejectedValue(new Error('Result read failed'))
      return new Response(frame({ type: 'complete', summary_id: READY.id }))
    }))
    const view = mount()
    await waitFor(() => expect(view.result.current.generationError).toBe('The summary could not load. Try again.'))
    expect(view.result.current.isStreaming).toBe(false)
  })

  it('reconciles terminal persisted progress when the SSE completion never arrives', async () => {
    let signal: AbortSignal | undefined
    mocks.progress.mockResolvedValue({ stage: 'completed', elapsedSeconds: 8 })
    vi.stubGlobal('fetch', vi.fn(async (_url, init: RequestInit) => {
      signal = init.signal as AbortSignal
      mocks.summary.mockResolvedValue(READY)
      return new Response(new ReadableStream())
    }))
    const view = mount()
    await waitFor(() => expect(view.result.current.summary?.id).toBe(READY.id))
    expect(view.result.current.isStreaming).toBe(false)
    expect(signal?.aborted).toBe(true)
  })

  it('releases a reader on unmount without starting another attempt', async () => {
    let signal: AbortSignal | undefined
    const fetch = vi.fn(async (_url, init: RequestInit) => {
      signal = init.signal as AbortSignal
      return new Response(new ReadableStream())
    })
    vi.stubGlobal('fetch', fetch)
    const view = mount()
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    view.unmount()
    await act(async () => { await Promise.resolve() })
    expect(signal?.aborted).toBe(true)
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('reserves force for explicit regeneration of an existing result', async () => {
    mocks.summary.mockResolvedValue(READY)
    const fetch = vi.fn(async (_url: string) => errorStream())
    vi.stubGlobal('fetch', fetch)
    const view = mount()
    await waitFor(() => expect(view.result.current.summary).toEqual(READY))
    await act(async () => { view.result.current.handleRetrySummary() })
    expect(fetch).not.toHaveBeenCalled()
    await act(async () => { view.result.current.handleRegenerateSummary() })
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    expect(String(fetch.mock.calls[0]?.[0])).toContain('force=true')
  })

  it('keeps the cooldown control focusable and refuses its activation', () => {
    const retry = vi.fn()
    const view = render(<StreamingSummaryDisplay filing={filing} streamingText="" stage="error"
      message={LIMITED} error={LIMITED} onRetry={retry} retryAfterSeconds={30} />)
    const button = screen.getByRole('button', { name: 'Try again' })
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).not.toBeDisabled()
    button.focus()
    fireEvent.click(button)
    expect(retry).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(button)
    view.rerender(<StreamingSummaryDisplay filing={filing} streamingText="" stage="error"
      message={LIMITED} error={LIMITED} onRetry={retry} retryAfterSeconds={0} />)
    fireEvent.click(button)
    expect(retry).toHaveBeenCalledOnce()
  })
})

describe('typed stream failures', () => {
  it('cancels a pending transport retry when its reader leaves', async () => {
    const fetch = vi.fn(async () => new Response(''))
    vi.stubGlobal('fetch', fetch)
    const controller = new AbortController()
    const error = vi.fn()
    const progress = vi.fn(() => controller.abort())
    await expect(generateSummaryStream(filing.id, vi.fn(), progress, vi.fn(), error,
      { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetch).toHaveBeenCalledOnce()
    expect(error).not.toHaveBeenCalled()
  })

  it('honors a body-only cooldown longer than the fallback and typed pause wording', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ detail: 'Wait for capacity.',
      code: 'summary_rate_limited', retry_after_seconds: 90 }), { status: 429 }))
    vi.stubGlobal('fetch', fetch)
    const error = vi.fn()
    await expect(generateSummaryStream(filing.id, vi.fn(), vi.fn(), vi.fn(), error)).rejects.toThrow()
    expect(error.mock.calls[0][1]).toMatchObject({ retryAfterSeconds: 90 })
    fetch.mockResolvedValue(new Response(JSON.stringify({ detail: 'Maintenance is in progress.',
      code: 'generation_paused' }), { status: 503 }))
    await expect(generateSummaryStream(filing.id, vi.fn(), vi.fn(), vi.fn(), error)).rejects.toThrow()
    expect(fetch).toHaveBeenCalledTimes(2)
  })
  it('keeps a source cooldown from SSE and does not replay it', async () => {
    const fetch = vi.fn(async () => new Response(frame({ type: 'error', message: GENERIC,
      code: 'sec_rate_limited', retry_after_seconds: 17, request_id: 'source-request' })))
    vi.stubGlobal('fetch', fetch)
    const error = vi.fn()
    await expect(generateSummaryStream(filing.id, vi.fn(), vi.fn(), vi.fn(), error)).rejects.toThrow(GENERIC)
    expect(error).toHaveBeenCalledWith(GENERIC, { code: 'sec_rate_limited', retryAfterSeconds: 17, requestId: 'source-request' })
    expect(fetch).toHaveBeenCalledOnce()
  })

  it('parses a server cooldown without rounding it down', () => {
    expect(summaryRetryAfter('1.2')).toBe(2)
    expect(summaryRetryAfter('nonsense')).toBeUndefined()
    expect(summaryRetryAfter(-1)).toBeUndefined()
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-30T11:05:00Z'))
    expect(summaryRetryAfter('Fri, 30 Oct 2026 11:06:00 GMT')).toBe(60)
  })
})
