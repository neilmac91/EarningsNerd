import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const refresh = vi.hoisted(() => ({ run: (): Promise<void> => Promise.resolve() }))
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: () => refresh.run() }))
import { generateSummaryStream } from '@/features/summaries/api/summaries-api'

const encoder = new TextEncoder()
const frame = (data: object) => `data: ${JSON.stringify(data)}\n\n`

// Real byte streams exercise decoder buffering and cancellation, rather than mocking the parser.
const response = (parts: string[], keepOpen = false) => {
  let cancelled = false
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      parts.forEach((part) => controller.enqueue(encoder.encode(part)))
      if (!keepOpen) controller.close()
    },
    cancel() { cancelled = true },
  })
  return { value: new Response(body), wasCancelled: () => cancelled, body }
}

const observe = () => {
  const chunk = vi.fn(), progress = vi.fn(), complete = vi.fn(), error = vi.fn()
  const state = { settled: false, failed: false }
  const promise = generateSummaryStream(101, chunk, progress, complete, error).then(
    () => { state.settled = true },
    () => { state.settled = true; state.failed = true },
  )
  return { chunk, progress, complete, error, state, promise }
}

describe('summary stream connection and terminal lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    window.localStorage.clear()
    refresh.run = () => Promise.resolve()
  })
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  it.each(['headers', 'refresh', 'body'] as const)('bounds a stalled %s phase and only retries once', async (phase) => {
    let requests = 0
    const signals: AbortSignal[] = []
    let finishRefresh = () => {}
    refresh.run = () => new Promise<void>((resolve) => { finishRefresh = resolve })
    if (phase === 'refresh') window.localStorage.setItem('en_session_active', '1')
    vi.stubGlobal('fetch', (_url: unknown, init: RequestInit) => {
      const signal = init.signal as AbortSignal
      signals.push(signal)
      if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
      requests += 1
      if (phase === 'headers') return new Promise<Response>(() => {})
      if (phase === 'refresh') return Promise.resolve(new Response('{}', { status: 401 }))
      return Promise.resolve(response([], true).value)
    })
    const result = observe()
    await vi.advanceTimersByTimeAsync(241200)
    finishRefresh()
    await Promise.resolve()
    expect(result.state).toEqual({ settled: true, failed: true })
    expect(requests).toBe(2)
    expect(signals.every((signal) => signal.aborted)).toBe(true)
    expect(result.complete).not.toHaveBeenCalled()
    expect(result.error).toHaveBeenCalledOnce()
    expect(result.error).toHaveBeenCalledWith(expect.stringMatching(/timed out/i))
    expect(vi.getTimerCount()).toBe(0)
  })

  it('retries an empty premature EOF once and then surfaces failure', async () => {
    const fetch = vi.fn(async () => response([]).value)
    vi.stubGlobal('fetch', fetch)
    const result = observe()
    await vi.runAllTimersAsync()
    await result.promise
    expect(result.state.failed).toBe(true)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(result.complete).not.toHaveBeenCalled()
    expect(result.error).toHaveBeenCalledWith(expect.stringMatching(/closed before the summary finished/i))
  })

  it.each(['chunk', 'preview'] as const)('never replays after a visible %s followed by premature EOF', async (type) => {
    const content = type === 'chunk' ? { content: 'Visible result' } : { markdown: 'Visible result' }
    const fetch = vi.fn(async () => response([frame({ type, ...content })]).value)
    vi.stubGlobal('fetch', fetch)
    const result = observe()
    await vi.runAllTimersAsync()
    await result.promise
    expect(result.state.failed).toBe(true)
    expect(result.chunk).toHaveBeenCalledWith('Visible result')
    expect(fetch).toHaveBeenCalledOnce()
    expect(result.complete).not.toHaveBeenCalled()
    expect(result.error).toHaveBeenCalledOnce()
  })

  it.each(['complete', 'partial'] as const)('accepts a split %s frame without its final newline', async (type) => {
    const text = `data: ${JSON.stringify({ type, summary_id: 42 })}`
    vi.stubGlobal('fetch', async () => response([text.slice(0, 17), text.slice(17)]).value)
    const result = observe()
    await result.promise
    expect(result.state.failed).toBe(false)
    expect(result.complete).toHaveBeenCalledExactlyOnceWith(42)
    expect(result.error).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('finishes once at a terminal frame even when the transport stays open', async () => {
    const stream = response([frame({ type: 'complete', summary_id: 42 }) + frame({ type: 'complete', summary_id: 99 })], true)
    vi.stubGlobal('fetch', async () => stream.value)
    const result = observe()
    await vi.advanceTimersByTimeAsync(0)
    expect(result.state).toEqual({ settled: true, failed: false })
    expect(result.complete).toHaveBeenCalledExactlyOnceWith(42)
    expect(stream.wasCancelled()).toBe(true)
    expect(stream.body.locked).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('rejects an invalid terminal ID without calling completion', async () => {
    vi.stubGlobal('fetch', async () => response([frame({ type: 'complete', summary_id: '42' })]).value)
    const result = observe()
    await vi.runAllTimersAsync()
    await result.promise
    expect(result.state.failed).toBe(true)
    expect(result.complete).not.toHaveBeenCalled()
    expect(result.error).toHaveBeenCalledWith(expect.stringMatching(/invalid completion/i))
  })

  it('surfaces an error after a preview without retrying or waiting for EOF', async () => {
    const fetch = vi.fn(async () => response([
      frame({ type: 'preview', markdown: 'Preview' }),
      frame({ type: 'error', message: 'Provider unavailable' }),
    ], true).value)
    vi.stubGlobal('fetch', fetch)
    const result = observe()
    await vi.advanceTimersByTimeAsync(0)
    expect(result.state).toEqual({ settled: true, failed: true })
    expect(fetch).toHaveBeenCalledOnce()
    expect(result.complete).not.toHaveBeenCalled()
    expect(result.error).toHaveBeenCalledExactlyOnceWith('Provider unavailable')
    expect(vi.getTimerCount()).toBe(0)
  })
})
