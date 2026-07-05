/**
 * streamAnalysis — SSE parsing contract against the backend event shapes
 * (progress/token/complete/error, mirroring trend_analysis_service.stream_trend_narrative).
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamAnalysis } from '@/features/analysis/api/analysis-api'

const originalFetch = global.fetch

const streamOf = (frames: Array<Record<string, unknown>>) => {
  const encoder = new TextEncoder()
  const chunks = frames.map((f) => encoder.encode(`data: ${JSON.stringify(f)}\n\n`))
  let readIndex = 0
  return {
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

describe('streamAnalysis', () => {
  afterEach(() => {
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

  it('flushes buffered tokens when a stream ends without a terminal event', async () => {
    // A terminal `complete` supersedes buffered tokens (the resolved narrative replaces the raw
    // stream), so live token delivery is asserted on a tokens-only stream: the graceful
    // end-of-stream flush must deliver the tail rather than dropping the final words.
    mockFetch([
      { type: 'token', text: 'Revenue grew ' },
      { type: 'token', text: 'steadily [F3].' },
    ])
    const tokens: string[] = []
    await streamAnalysis('AAPL', RANGE, {
      onToken: (t) => tokens.push(t),
      onComplete: vi.fn(),
      onError: vi.fn(),
    })
    expect(tokens.join('')).toBe('Revenue grew steadily [F3].')
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
