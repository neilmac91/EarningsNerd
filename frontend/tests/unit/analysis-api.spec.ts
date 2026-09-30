/**
 * streamAnalysis — SSE parsing contract against the backend event shapes
 * (progress/token/complete/error, mirroring trend_analysis_service.stream_trend_narrative).
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createElement } from 'react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import api from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'

vi.mock('@/features/companies/components/CompanySearch', () => ({
  default: ({ onSelect }: { onSelect: (ticker: string) => void }) =>
    createElement('div', null,
      createElement('button', { onClick: () => onSelect('AAPL') }, 'Select Apple'),
      createElement('button', { onClick: () => onSelect('MSFT') }, 'Select Microsoft')),
}))
vi.mock('@/lib/analytics', () => ({ default: { analysisRun: vi.fn() } }))
import { streamAnalysis } from '@/features/analysis/api/analysis-api'

const originalFetch = global.fetch

const streamOf = (frames: Array<Record<string, unknown>>) => {
  const encoder = new TextEncoder()
  const chunks = frames.map((f) => encoder.encode(`data: ${JSON.stringify(f)}\n\n`))
  let readIndex = 0
  return {
    cancel: vi.fn(async () => {}),
    releaseLock: vi.fn(),
    read: vi.fn(async () =>
      readIndex < chunks.length
        ? { value: chunks[readIndex++], done: false }
        : { value: undefined, done: true }
    ),
  }
}

const mockFetch = (frames: Array<Record<string, unknown>>) => {
  global.fetch = vi.fn(async () => ({
    ok: true,
    body: { getReader: () => streamOf(frames) },
  })) as unknown as typeof fetch
}

const RANGE = { mode: 'annual' as const, start_period: 'FY2021', end_period: 'FY2023' }

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const datasetResponse = (ticker: string) => ({ data: {
  ticker, company_name: ticker, mode: 'annual', period_key: 'FY2021..FY2023',
  periods: [], series: [], inflections: [],
} })

function mountAnalysis() {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
  client.setQueryData(queryKeys.currentUser(), { id: 7 })
  client.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
  for (const ticker of ['AAPL', 'MSFT']) {
    client.setQueryData(queryKeys.analysisCoverage(ticker), {
      ticker, company_name: ticker, supported: true, syncing: false,
      annual: [2021, 2022, 2023].map((year) => ({ key: `FY${year}`, fiscal_year: year, period_end: `${year}-12-31`, has_core: true })),
      quarterly: [{ key: 'Q1-2023', fiscal_year: 2023, fiscal_period: 'Q1', period_end: '2023-03-31', derived: false }],
      limits: { annual: 10, quarterly: 12 },
    })
  }
  const view = render(createElement(QueryClientProvider, { client }, createElement(AnalysisPageClient)))
  return { ...view, client }
}

describe('streamAnalysis', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    global.fetch = originalFetch
  })

  it('drives progress/complete and posts the range body', async () => {
    mockFetch([
      { type: 'progress', stage: 'assembling' },
      { type: 'token', text: 'Revenue grew ' },
      { type: 'token', text: 'steadily [F3].' },
      {
        type: 'complete',
        kind: 'analysis',
        analysis_id: 7,
        narrative: 'Revenue grew steadily [1].',
        citations: [{ n: 1, excerpt: 'Revenue = 1', section_ref: 'XBRL · x', verified: true, fragment_url: null }],
        grounded: 1,
        cached: false,
        n_periods: 3,
      },
    ])

    const progress = vi.fn()
    const complete = vi.fn()
    const error = vi.fn()
    await streamAnalysis('AAPL', { ...RANGE, force: true }, {
      onProgress: progress,
      onToken: vi.fn(),
      onComplete: complete,
      onError: error,
    })

    expect(progress).toHaveBeenCalledWith('assembling')
    expect(complete).toHaveBeenCalledTimes(1)
    const completion = complete.mock.calls[0][0]
    expect(completion.kind).toBe('analysis')
    expect(completion.analysis_id).toBe(7)
    expect(completion.cached).toBe(false)
    expect(completion.citations).toHaveLength(1)
    expect(error).not.toHaveBeenCalled()

    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(String(url)).toContain('/api/analysis/AAPL/stream')
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      mode: 'annual',
      start_period: 'FY2021',
      end_period: 'FY2023',
      force: true,
    })
  })

  it.each([{ frames: [] }, { frames: [{ type: 'token', text: 'Incomplete draft' }] }])(
    'reports EOF without a terminal event once: $frames',
    async ({ frames }) => {
      mockFetch(frames)
      const complete = vi.fn()
      const error = vi.fn()
      await streamAnalysis('AAPL', RANGE, { onToken: vi.fn(), onComplete: complete, onError: error })
      expect(error).toHaveBeenCalledTimes(1)
      expect(error).toHaveBeenCalledWith(expect.stringMatching(/ended before.*complete/i))
      expect(complete).not.toHaveBeenCalled()
    },
  )

  it.each(['timeout', 'caller'] as const)('settles an idle stream on %s abort', async (cause) => {
    vi.useFakeTimers()
    const caller = new AbortController()
    let rejectRead: (error: Error) => void = () => {}
    const reader = {
      read: vi.fn(() => new Promise<ReadableStreamReadResult<Uint8Array>>((_resolve, reject) => {
        rejectRead = reject
      })),
      cancel: vi.fn(async () => {}),
      releaseLock: vi.fn(),
    }
    global.fetch = vi.fn(async (_url, init) => {
      init?.signal?.addEventListener('abort', () => rejectRead(new DOMException('Aborted', 'AbortError')))
      return { ok: true, body: { getReader: () => reader } }
    }) as unknown as typeof fetch
    const error = vi.fn()
    const complete = vi.fn()
    const request = streamAnalysis('AAPL', RANGE, {
      onToken: vi.fn(), onComplete: complete, onError: error,
    }, caller.signal)
    await vi.advanceTimersByTimeAsync(0)
    expect(reader.read).toHaveBeenCalledTimes(1)
    if (cause === 'caller') caller.abort()
    else await vi.advanceTimersByTimeAsync(120_000)
    await request
    expect(complete).not.toHaveBeenCalled()
    if (cause === 'caller') expect(error).not.toHaveBeenCalled()
    else {
      expect(error).toHaveBeenCalledTimes(1)
      expect(error).toHaveBeenCalledWith(expect.stringMatching(/timed out/i))
    }
    expect(reader.cancel).toHaveBeenCalledTimes(1)
    expect(reader.releaseLock).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['complete', 'error'] as const)('stops after the first %s terminal event', async (type) => {
    const first = type === 'complete'
      ? { type, kind: 'analysis', narrative: 'Final answer', citations: [], grounded: 0, n_periods: 2 }
      : { type, message: 'Generation failed.' }
    const reader = streamOf([first, { type: 'token', text: 'Late draft' }, first])
    global.fetch = vi.fn(async () => ({ ok: true, body: { getReader: () => reader } })) as unknown as typeof fetch
    const complete = vi.fn()
    const error = vi.fn()
    const token = vi.fn()
    await streamAnalysis('AAPL', RANGE, { onToken: token, onComplete: complete, onError: error })
    expect(complete).toHaveBeenCalledTimes(type === 'complete' ? 1 : 0)
    expect(error).toHaveBeenCalledTimes(type === 'error' ? 1 : 0)
    expect(token).not.toHaveBeenCalled()
    expect(reader.read).toHaveBeenCalledTimes(1)
    expect(reader.cancel).toHaveBeenCalledTimes(1)
    expect(reader.releaseLock).toHaveBeenCalledTimes(1)
  })

  it('stops callbacks when the caller cancels within a received chunk', async () => {
    const caller = new AbortController()
    const reader = streamOf([])
    reader.read.mockResolvedValueOnce({ done: false, value: new TextEncoder().encode([
      { type: 'progress', stage: 'assembling' },
      { type: 'token', text: 'Late draft' },
      { type: 'complete', narrative: 'Late completion' },
    ].map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')) })
    global.fetch = vi.fn(async () => ({ ok: true, body: { getReader: () => reader } })) as unknown as typeof fetch
    const token = vi.fn()
    const complete = vi.fn()
    const error = vi.fn()
    await streamAnalysis('AAPL', RANGE, {
      onProgress: () => caller.abort(), onToken: token, onComplete: complete, onError: error,
    }, caller.signal)
    expect(token).not.toHaveBeenCalled()
    expect(complete).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    expect(reader.read).toHaveBeenCalledTimes(1)
    expect(reader.cancel).toHaveBeenCalledTimes(1)
    expect(reader.releaseLock).toHaveBeenCalledTimes(1)
  })

  it('delivers live previews before a successful authoritative completion', async () => {
    let frame: FrameRequestCallback = () => {}
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { frame = callback; return 1 }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    let finishRead: (result: ReadableStreamReadResult<Uint8Array>) => void = () => {}
    const reader = streamOf([{ type: 'token', text: 'Live preview' }])
    reader.read.mockImplementationOnce(async () => ({
      done: false, value: new TextEncoder().encode('data: {"type":"token","text":"Live preview"}\n\n'),
    })).mockImplementationOnce(() => new Promise((resolve) => { finishRead = resolve }))
    global.fetch = vi.fn(async () => ({ ok: true, body: { getReader: () => reader } })) as unknown as typeof fetch
    const token = vi.fn()
    const complete = vi.fn()
    const error = vi.fn()
    const request = streamAnalysis('AAPL', RANGE, { onToken: token, onComplete: complete, onError: error })
    await waitFor(() => expect(reader.read).toHaveBeenCalledTimes(2))
    frame(0)
    expect(token).toHaveBeenCalledWith('Live preview')
    finishRead({ done: false, value: new TextEncoder().encode('data: {"type":"complete","narrative":"Final answer"}\n\n') })
    await request
    expect(complete).toHaveBeenCalledTimes(1)
    expect(complete.mock.calls[0][0].narrative).toBe('Final answer')
    expect(error).not.toHaveBeenCalled()
  })

  it('releases the actual mounted Run control after incomplete EOF', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
    queryClient.setQueryData(queryKeys.currentUser(), { id: 7 })
    queryClient.setQueryData(queryKeys.subscription.byUser(7), { is_pro: true })
    queryClient.setQueryData(queryKeys.analysisCoverage('AAPL'), {
      ticker: 'AAPL', company_name: 'Apple', supported: true, syncing: false,
      annual: [{ key: 'FY2023', fiscal_year: 2023, period_end: '2023-09-30', has_core: true }],
      quarterly: [], limits: { annual: 10, quarterly: 12 },
    })
    vi.spyOn(api, 'post').mockResolvedValue({ data: {
      ticker: 'AAPL', company_name: 'Apple', mode: 'annual', period_key: 'FY2023..FY2023',
      periods: [], series: [], inflections: [],
    } })
    let end: (result: ReadableStreamReadResult<Uint8Array>) => void = () => {}
    const reader = streamOf([])
    reader.read.mockImplementationOnce(() => new Promise((resolve) => { end = resolve }))
    global.fetch = vi.fn(async () => ({ ok: true, body: { getReader: () => reader } })) as unknown as typeof fetch
    render(createElement(QueryClientProvider, { client: queryClient }, createElement(AnalysisPageClient)))
    fireEvent.click(screen.getByRole('button', { name: 'Select Apple' }))
    const run = await screen.findByRole('button', { name: 'Run analysis' })
    await waitFor(() => expect(run).toBeEnabled())
    fireEvent.click(run)
    await waitFor(() => expect(reader.read).toHaveBeenCalledTimes(1))
    expect(run).toBeDisabled()
    await act(async () => { end({ done: true, value: undefined }) })
    await waitFor(() => expect(run).toBeEnabled())
    expect(screen.getByRole('alert')).toHaveTextContent(/ended before.*complete/i)
    expect(screen.queryByText('Assembling the numbers…')).not.toBeInTheDocument()
    queryClient.clear()
  })

  it.each(['company', 'mode', 'range', 'unmount'] as const)(
    'does not launch an obsolete narrative after %s changes during dataset loading', async (change) => {
      const pending = deferred<ReturnType<typeof datasetResponse>>()
      const post = vi.spyOn(api, 'post').mockReturnValue(pending.promise)
      mockFetch([])
      const view = mountAnalysis()
      fireEvent.click(screen.getByRole('button', { name: 'Select Apple' }))
      const run = await screen.findByRole('button', { name: 'Run analysis' })
      await waitFor(() => expect(run).toBeEnabled())
      fireEvent.click(run)
      await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
      if (change === 'company') fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
      if (change === 'mode') fireEvent.click(screen.getByRole('button', { name: 'Quarterly' }))
      if (change === 'range') fireEvent.click(screen.getByRole('button', { name: 'FY2022' }))
      if (change === 'unmount') view.unmount()
      // Deliberately resolve despite cancellation: stale-result ownership must not depend
      // on a transport honoring AbortSignal before it settles.
      await act(async () => { pending.resolve(datasetResponse('AAPL')) })
      expect(global.fetch).not.toHaveBeenCalled()
      expect(screen.queryByRole('heading', { name: 'AI trend analysis' })).not.toBeInTheDocument()
      expect(post.mock.calls[0][2]?.signal?.aborted).toBe(true)
      view.client.clear()
    },
  )

  it.each(['success', 'error'] as const)('ignores an old dataset %s while the new company is streaming', async (outcome) => {
    const old = deferred<ReturnType<typeof datasetResponse>>()
    vi.spyOn(api, 'post').mockReturnValueOnce(old.promise).mockResolvedValueOnce(datasetResponse('MSFT'))
    const nextFrame = deferred<ReadableStreamReadResult<Uint8Array>>()
    const reader = streamOf([])
    reader.read.mockImplementationOnce(() => nextFrame.promise)
    global.fetch = vi.fn(async () => ({ ok: true, body: { getReader: () => reader } })) as unknown as typeof fetch
    const view = mountAnalysis()
    fireEvent.click(screen.getByRole('button', { name: 'Select Apple' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Run analysis' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    fireEvent.click(screen.getByRole('button', { name: 'Select Microsoft' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Run analysis' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => expect(reader.read).toHaveBeenCalledTimes(1))
    const fetchMock = vi.mocked(global.fetch)
    const activeSignal = fetchMock.mock.calls[0][1]?.signal
    expect(String(fetchMock.mock.calls[0][0])).toContain('/MSFT/stream')
    await act(async () => {
      if (outcome === 'success') old.resolve(datasetResponse('AAPL'))
      else old.reject(new Error('Old request failed'))
    })
    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(activeSignal?.aborted).toBe(false)
    expect(screen.getByRole('button', { name: 'Run analysis' })).toBeDisabled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(async () => { nextFrame.resolve({ done: false, value: new TextEncoder().encode(
      'data: {"type":"complete","kind":"analysis","narrative":"Current Microsoft result","citations":[],"grounded":0,"cached":true,"n_periods":2}\n\n',
    ) }) })
    expect(await screen.findByText('Current Microsoft result')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run analysis' })).toBeEnabled()
    view.client.clear()
  })

  it('routes an error event to onError and drops buffered tokens', async () => {
    mockFetch([
      { type: 'token', text: 'partial' },
      { type: 'error', message: 'The analysis could not be generated.' },
    ])
    const complete = vi.fn()
    const error = vi.fn()
    await streamAnalysis('AAPL', RANGE, {
      onToken: vi.fn(),
      onComplete: complete,
      onError: error,
    })
    expect(error).toHaveBeenCalledWith('The analysis could not be generated.')
    expect(complete).not.toHaveBeenCalled()
  })

  it('surfaces the 403 paywall detail without reading a stream', async () => {
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Multi-Period Analysis is a Pro feature. Upgrade to Pro to access this feature.' }),
    })) as unknown as typeof fetch

    const error = vi.fn()
    await streamAnalysis('AAPL', RANGE, {
      onToken: vi.fn(),
      onComplete: vi.fn(),
      onError: error,
    })
    expect(error).toHaveBeenCalledTimes(1)
    expect(String(error.mock.calls[0][0])).toContain('Pro feature')
  })

  it('maps not_enough_data completions through', async () => {
    mockFetch([
      { type: 'complete', kind: 'not_enough_data', analysis_id: null, narrative: '', citations: [], grounded: 0, cached: false, n_periods: 1 },
    ])
    const complete = vi.fn()
    await streamAnalysis('AAPL', RANGE, {
      onToken: vi.fn(),
      onComplete: complete,
      onError: vi.fn(),
    })
    expect(complete.mock.calls[0][0].kind).toBe('not_enough_data')
  })
})
