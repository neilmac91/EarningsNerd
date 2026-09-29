import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { askFilingStream, type CopilotHandlers, type CopilotCompletion } from '@/features/filings/api/copilot-api'

const auth = vi.hoisted(() => ({ active: false, refresh: async () => {} }))
vi.mock('@/lib/api/client', () => ({ getApiUrl: () => 'https://api.example.test', ensureRefreshed: () => auth.refresh() }))
vi.mock('@/lib/api/session', () => ({
  hasActiveSession: () => auth.active, getSessionGeneration: () => 1,
  isSessionGenerationCurrent: () => true, notifySessionLost: () => {},
}))

function handlers(): CopilotHandlers {
  return { onToken: vi.fn(), onComplete: vi.fn(), onError: vi.fn(), onNotDisclosed: vi.fn(), onProgress: vi.fn() }
}
const enc = new TextEncoder()
const sse = (obj: unknown) => `data: ${JSON.stringify(obj)}\n\n`
const completion: CopilotCompletion = {
  answer: '**Revenue** was $10 million [1].',
  citations: [{ n: 1, excerpt: 'Revenue was $10 million.', section_ref: 'MD&A', verified: true, fragment_url: null }],
  grounded: 1, kind: 'answer', followups: ['What were the costs?'],
}
const notDisclosed: CopilotCompletion = {
  answer: 'The filing does not disclose this.', citations: [], grounded: 0, kind: 'not_disclosed',
  followups: ['What were the costs?', 'How did revenue change?'],
}
function stream() {
  let control!: ReadableStreamDefaultController<Uint8Array>
  const cancel = vi.fn()
  const body = new ReadableStream<Uint8Array>({ start(c) { control = c }, cancel })
  return { response: new Response(body), send: (text: string) => control.enqueue(enc.encode(text)), close: () => control.close(), cancel }
}
async function settle() { for (let i = 0; i < 12; i++) await Promise.resolve() }

// Exercise the real refresh owner and real SSE consumer; no provider calls.
describe('askFilingStream completion-only publication and lifecycle', () => {
  const originalFetch = global.fetch
  beforeEach(() => { vi.useFakeTimers(); auth.active = false; auth.refresh = async () => {} })
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks(); global.fetch = originalFetch })

  it('holds old-backend draft and not-disclosed bytes until a valid chunked completion', async () => {
    const wire = stream()
    global.fetch = async () => wire.response
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    wire.send(sse({ type: 'token', text: 'UNADMITTED DRAFT' }) + sse({ type: 'not_disclosed', answer: 'UNADMITTED ABSENCE' }))
    wire.send(sse({ type: 'progress', stage: 'MODEL DRAFT' }) + sse({ type: 'activity', label: 'MODEL ARGUMENT' }))
    await settle()
    expect(h.onToken).not.toHaveBeenCalled()
    expect(h.onNotDisclosed).not.toHaveBeenCalled()
    expect(h.onComplete).not.toHaveBeenCalled()
    expect(h.onProgress).toHaveBeenCalledWith('reading')
    const final = sse({ type: 'complete', ...completion })
    for (const char of final) wire.send(char)
    await task
    expect(h.onComplete).toHaveBeenCalledExactlyOnceWith(completion)
    expect(h.onError).not.toHaveBeenCalled()
    expect(wire.cancel).toHaveBeenCalledOnce()
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each([
    ['known-false source', { citations: [{ ...completion.citations[0], verified: false }] }],
    ['missing source verdict', { citations: [{ ...completion.citations[0], verified: undefined }] }],
    ['invalid source identity', { citations: [{ ...completion.citations[0], n: true }] }],
    ['missing excerpt', { citations: [{ ...completion.citations[0], excerpt: null }] }],
    ['missing section reference', { citations: [{ ...completion.citations[0], section_ref: undefined }] }],
    ['duplicate source', { citations: [completion.citations[0], completion.citations[0]] }],
    ['non-array citations', { citations: {} }],
    ['invalid followups', { followups: [123] }],
    ['unknown verdict', { kind: 'maybe' }],
    ['nonfinite count', { grounded: Infinity }],
    ['mixed non-disclosure', { kind: 'not_disclosed' }],
    ['empty non-disclosure followups', { ...notDisclosed, followups: [] }],
    ['one non-disclosure followup', { ...notDisclosed, followups: ['What were the costs?'] }],
    ['too many non-disclosure followups', { ...notDisclosed, followups: ['First?', 'Second?', 'Third?', 'Fourth?'] }],
    ['blank non-disclosure followup', { ...notDisclosed, followups: ['What were the costs?', ''] }],
    ['whitespace non-disclosure followup', { ...notDisclosed, followups: ['What were the costs?', ' \n\t '] }],
  ])('rejects a %s completion with no candidate content', async (_label, patch) => {
    const wire = stream()
    global.fetch = async () => wire.response
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    wire.send(sse({ type: 'token', text: 'private candidate' }) + sse({ type: 'complete', ...completion, ...patch }))
    await task
    expect(h.onComplete).not.toHaveBeenCalled()
    expect(h.onToken).not.toHaveBeenCalled()
    expect(h.onNotDisclosed).not.toHaveBeenCalled()
    expect(h.onError).toHaveBeenCalledExactlyOnceWith("I couldn't verify the cited evidence, so I couldn't provide this answer.")
    expect(wire.cancel).toHaveBeenCalledOnce()
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each([
    { answer: 'Ordinary uncited answer [14].', citations: [], grounded: 0, kind: 'answer', followups: [] },
    notDisclosed,
    { ...notDisclosed, followups: [...notDisclosed.followups, 'What are the risk factors?'] },
    { ...completion, answer: 'Revenue $10 million [1], costs $5 million [F2].', grounded: 2,
      citations: [...completion.citations, { n: 'F2', excerpt: 'Costs: USD 5000000', section_ref: 'XBRL · Costs', verified: true, fragment_url: null }] },
  ])('preserves valid final payload $kind with $grounded matched sources', async (payload) => {
    const wire = stream()
    global.fetch = async () => wire.response
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    wire.send(sse({ type: 'complete', ...payload }))
    await task
    expect(h.onComplete).toHaveBeenCalledExactlyOnceWith(payload)
    expect(h.onNotDisclosed).not.toHaveBeenCalled()
  })

  it.each(['complete', 'error'])('uses the first terminal %s and ignores later frames in the same chunk', async (first) => {
    const wire = stream()
    global.fetch = async () => wire.response
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    const done = sse({ type: 'complete', ...completion })
    const error = sse({ type: 'error', message: 'RAW MODEL DRAFT' })
    wire.send(first === 'complete' ? done + error + done : error + done + error)
    await task
    expect(h.onComplete).toHaveBeenCalledTimes(first === 'complete' ? 1 : 0)
    expect(h.onError).toHaveBeenCalledTimes(first === 'error' ? 1 : 0)
    if (first === 'error') expect(h.onError).toHaveBeenCalledWith('The answer could not be completed. Please try again.')
  })

  it.each(['eof', 'truncated', 'malformed', 'network'])('fails safely for %s and never flushes draft prose', async (failure) => {
    const wire = stream()
    global.fetch = failure === 'network' ? async () => { throw new Error('RAW MODEL DRAFT') } : async () => wire.response
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    if (failure !== 'network') {
      wire.send(sse({ type: 'token', text: 'RAW MODEL DRAFT' }))
      if (failure === 'truncated') wire.send('data: {"type":"complete","answer":"RAW MODEL DRAFT')
      if (failure === 'malformed') wire.send('data: {broken}\n')
      wire.close()
    }
    await task
    expect(h.onError).toHaveBeenCalledExactlyOnceWith('The answer could not be completed. Please try again.')
    expect(h.onToken).not.toHaveBeenCalled()
    expect(h.onComplete).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('resets the idle bound on activity without publishing draft bytes', async () => {
    const wire = stream()
    global.fetch = async () => wire.response
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    await vi.advanceTimersByTimeAsync(90000)
    wire.send(sse({ type: 'token', text: 'PRIVATE DRAFT' }))
    await settle()
    await vi.advanceTimersByTimeAsync(90000)
    expect(h.onError).not.toHaveBeenCalled()
    expect(h.onToken).not.toHaveBeenCalled()
    wire.send(sse({ type: 'complete', ...completion }))
    await task
    expect(h.onComplete).toHaveBeenCalledExactlyOnceWith(completion)
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['headers', 'refresh', 'body'])('times out while waiting for %s and suppresses late results', async (phase) => {
    const wire = stream()
    let release!: (response: Response) => void
    let refresh!: () => void
    const lateResponse = new Promise<Response>((resolve) => { release = resolve })
    const refreshDone = new Promise<void>((resolve) => { refresh = resolve })
    let posts = 0
    auth.active = phase === 'refresh'
    auth.refresh = () => refreshDone
    global.fetch = async () => {
      posts++
      if (phase === 'refresh' && posts === 1) return new Response(null, { status: 401 })
      return phase === 'headers' ? lateResponse : wire.response
    }
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h)
    await settle()
    await vi.advanceTimersByTimeAsync(120000)
    await task
    expect(h.onError).toHaveBeenCalledExactlyOnceWith('The answer timed out. Please try again.')
    release(wire.response)
    refresh()
    await settle()
    expect(posts).toBe(1)
    expect(h.onComplete).not.toHaveBeenCalled()
    expect(h.onError).toHaveBeenCalledOnce()
    if (phase !== 'refresh') expect(wire.cancel).toHaveBeenCalledOnce()
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['headers', 'refresh', 'body'])('external cancellation during %s is quiet and disposes late work', async (phase) => {
    const wire = stream()
    let release!: (response: Response) => void
    let refresh!: () => void
    const lateResponse = new Promise<Response>((resolve) => { release = resolve })
    auth.refresh = () => new Promise<void>((resolve) => { refresh = resolve })
    auth.active = phase === 'refresh'
    let posts = 0
    global.fetch = async () => { posts++; return phase === 'headers' ? lateResponse : phase === 'refresh' ? new Response(null, { status: 401 }) : wire.response }
    const external = new AbortController()
    const removed = vi.spyOn(external.signal, 'removeEventListener')
    const h = handlers()
    const task = askFilingStream(1, 'q', [], h, external.signal)
    await settle()
    external.abort()
    await task
    release(wire.response)
    if (phase === 'refresh') refresh()
    await settle()
    expect(posts).toBe(1)
    expect(h.onError).not.toHaveBeenCalled()
    expect(h.onComplete).not.toHaveBeenCalled()
    expect(removed).toHaveBeenCalledWith('abort', expect.any(Function))
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each([401, 403, 429])('preserves HTTP %s entitlement behavior', async (status) => {
    global.fetch = async () => new Response(JSON.stringify({ detail: 'Monthly cap reached. Upgrade to Pro.' }), { status })
    const h = handlers()
    await askFilingStream(1, 'q', [], h)
    expect(h.onError).toHaveBeenCalledExactlyOnceWith(status === 401 ? 'Sign in to use the Copilot.' : 'Monthly cap reached. Upgrade to Pro.')
  })
})
