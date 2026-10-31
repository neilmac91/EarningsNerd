import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { generateSummaryStream, isNonRetryableStreamError, isPaywallStreamError } from '@/features/summaries/api/summaries-api'
import { ERROR_CODES, type KnownErrorCode } from '@/lib/api/client'
import { stripInternalNotices } from '@/lib/stripInternalNotices'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')

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
  // matcher to admission.py's sentence). Terminal errors are surfaced without replaying server-owned work.
  it("makes no automatic second attempt at a terminal application error", async () => {
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
    expect(await attempts('Provider unavailable')).toEqual({ requests: 1, shown: [['Provider unavailable']] })
  })

  // E31 (docs/audit/contracts/error-codes.md §6): admission's account refusals carry their code on the stream, and a known
  // code decides the card whatever its words; an absent code (a server before E31), an unknown one, or an HTTP-only code
  // on the stream reads as none, and the words decide as before.
  const refusedOnStream = async (frame: Record<string, unknown>) => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
    const fetchMock = vi.fn(async () => new Response(`data: ${JSON.stringify({ type: 'error', ...frame })}\n\n`))
    global.fetch = fetchMock as unknown as typeof fetch
    const errorSpy = vi.fn()
    const run = generateSummaryStream(303, vi.fn(), vi.fn(), vi.fn(), errorSpy).catch(() => undefined)
    await vi.runAllTimersAsync()
    await run
    return { requests: fetchMock.mock.calls.length, calls: errorSpy.mock.calls }
  }

  it.each([
    ['the free allowance, in words that name no limit', 'Your free summaries are used up.', 'free_allowance_exhausted', true],
    ["Pro's fair-use cap, in words that name Pro", 'Upgrade to Pro will not lift this.', 'pro_fair_use_limit', false],
  ])('answers %s by its code', async (_, message, code, paywall) => {
    const { requests, calls } = await refusedOnStream({ message, code })
    expect(requests).toBe(1)
    expect(calls).toHaveLength(1)
    const [shown, failure] = calls[0]
    expect([shown, failure?.code]).toEqual([message, code])
    expect(isPaywallStreamError(shown, failure?.code)).toBe(paywall)
    expect(isNonRetryableStreamError(shown, failure?.code)).toBe(true)
  })

  it.each([
    ['no code (a server before E31)', {}],
    ['an unknown code', { code: 'quota_v9' }],
    ['an HTTP-only code on the stream', { code: 'plan_required' }],
  ])('reads %s on the stream as none, and the words decide', async (_, extra) => {
    const quota = "You've reached your monthly limit of 5 summaries. Upgrade to Pro for unlimited summaries."
    const { calls } = await refusedOnStream({ message: quota, ...extra })
    expect(calls).toEqual([[quota]])
    expect(isPaywallStreamError(quota)).toBe(true)
  })

  it('keeps a 401 retryable by its words whatever its code, as the contract keeps its Retry', () => {
    expect(isNonRetryableStreamError('You are not logged in.', 'auth_required')).toBe(false)
    expect(isNonRetryableStreamError('You are not logged in.')).toBe(false)
    expect(isNonRetryableStreamError('Regenerating a summary is a Pro feature.', 'plan_required')).toBe(true)
  })

  // The E31 contract's §3, code by code, read from its own table: whether the card withholds its Retry for a refusal
  // carrying the code, which decides first whatever the words. A row's "Client behaviour" cell that says "never offer
  // Retry" withholds it, the one phrase that does: any other negation of Retry ("do not offer Retry", "no Retry",
  // "Retry is never offered") fails rather than reads as a kept Retry. A cell that keeps a Retry, waits out a
  // Retry-After or a cooldown, or lets a retry follow keeps it (`auth_required`'s "Retry included": today's 401
  // handling, its words deciding).
  const SECTION_3 = (() => {
    const doc = readFileSync(path.join(REPO, 'docs/audit/contracts/error-codes.md'), 'utf8')
    const section = doc.slice(doc.indexOf('## 3.'), doc.indexOf('## 4.'))
    return new Map(section.split('\n').filter((line) => line.startsWith('| `')).map((line) => {
      const cells = line.split(/(?<!\\)\|/).slice(1, -1).map((cell) => cell.trim()) // GFM escapes a cell's own pipe
      if (cells.length !== 4) throw new Error(`§3 row with ${cells.length} cells: ${line.slice(0, 60)}`)
      return [cells[0].replace(/`/g, ''), cells[3]] as const
    }))
  })()
  const NEGATED_RETRY = /\b(?:no|not|never|without)\b[^.;,:]{0,25}\bretr(?:y|ies)\b|\bretr(?:y|ies)\b[^.;,:]{0,25}\b(?:never|not)\b/i
  const section3Withholds = (code: string, cell: string): boolean | null => {
    if (/never offer Retry/.test(cell)) return true
    if (NEGATED_RETRY.test(cell)) throw new Error(`§3's ${code} row negates Retry in other words: write "never offer Retry"`)
    return /\bRetry\b|\bretry\b|cooldown/.test(cell) ? false : null
  }
  // §3 states no Retry rule for these, so they hold the reader's verdict: a gate the checkout raises, and the
  // calendar's own reader's code.
  const READER_VERDICT_WHERE_SECTION_3_IS_SILENT: Partial<Record<KnownErrorCode, boolean>> = {
    email_verification_required: true,
    earnings_alert_limit: false,
  }
  // #1824 ships `generation_paused` as non-retryable, where §3's row gives it a Retry: reported on #1848 for the
  // contract's owner to settle. Named so that any other disagreement fails, and so does this one once it is settled,
  // in the reader or in §3.
  const DISAGREES_WITH_SECTION_3: KnownErrorCode[] = ['generation_paused']

  it('reads a Retry rule, or names the silence, for every known code in §3', () => {
    expect([...SECTION_3.keys()].sort(), '§3 has a row for each known code, and only those').toEqual(Object.keys(ERROR_CODES).sort())
    const silent = [...SECTION_3].filter(([code, cell]) => section3Withholds(code, cell) === null).map(([code]) => code)
    expect(silent.sort(), 'a §3 row with no Retry rule takes the reader verdict here, and only such a row')
      .toEqual(Object.keys(READER_VERDICT_WHERE_SECTION_3_IS_SILENT).sort())
  })

  it.each(Object.keys(ERROR_CODES) as KnownErrorCode[])('holds %s\'s Retry verdict to §3, its named silence or its named disagreement', (code) => {
    const contract = section3Withholds(code, SECTION_3.get(code) ?? '') ?? READER_VERDICT_WHERE_SECTION_3_IS_SILENT[code]
    expect(contract, `classify ${code}: give §3's row a Retry rule, or name the reader's verdict here`).toBeTypeOf('boolean')
    const verdict = isNonRetryableStreamError('A sentence no matcher reads.', code)
    expect(verdict, DISAGREES_WITH_SECTION_3.includes(code)
      ? `${code} now agrees with §3: drop it from DISAGREES_WITH_SECTION_3`
      : `${code}'s verdict disagrees with §3`).toBe(DISAGREES_WITH_SECTION_3.includes(code) ? !contract : contract)
  })

  const refusedOnHttp = async (status: number, body: Record<string, unknown>, headers: Record<string, string> = {}) => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status, headers }))
    global.fetch = fetchMock as unknown as typeof fetch
    const errorSpy = vi.fn()
    const run = generateSummaryStream(303, vi.fn(), vi.fn(), vi.fn(), errorSpy).catch(() => undefined)
    await vi.runAllTimersAsync()
    await run
    return { requests: fetchMock.mock.calls.length, calls: errorSpy.mock.calls }
  }

  // The same matrix on the HTTP channel, where a code counts only on its registered status (lib/api/client.ts).
  const regenerate = 'Regenerating a summary is a Pro feature.'
  it.each([
    ['a coded plan gate, in words that name no plan', 403, { detail: 'Only some readers may do that.', code: 'plan_required' }, 'plan_required'],
    ['a plan gate with no code (a server before E31)', 403, { detail: regenerate }, undefined],
    ['a 403 with an unknown code', 403, { detail: regenerate, code: 'quota_v9' }, undefined],
    ['a 403 carrying the fair-use code, registered on 429', 403, { detail: regenerate, code: 'pro_fair_use_limit' }, undefined],
    ['a 429 carrying the plan code, registered on 403', 429, { detail: 'Too many summary requests. Try again shortly.', code: 'plan_required' }, undefined],
  ])('reads %s by its registered status', async (_, status, body, code) => {
    const { requests, calls } = await refusedOnHttp(status, body)
    expect(requests).toBe(1)
    expect(calls).toHaveLength(1)
    expect([calls[0][0], calls[0][1]?.code]).toEqual([body.detail, code])
    // A 403 holds whatever the reader retries: by its code when it carries one, by its words when it does not.
    expect(isNonRetryableStreamError(calls[0][0], calls[0][1]?.code)).toBe(status === 403)
    expect(isPaywallStreamError(calls[0][0], calls[0][1]?.code)).toBe(false)
  })

  it.each([
    ['the fair-use cap, coded', { detail: 'Summary generation allowance is exhausted', code: 'pro_fair_use_limit' }, {}, undefined],
    ['the fair-use cap, coded, with a stated wait', { detail: 'Summary generation allowance is exhausted', code: 'pro_fair_use_limit' },
      { 'Retry-After': '120' }, 120],
    ['a plain rate limit', { detail: 'Too many summary requests. Try again shortly.' }, {}, 60],
    ['a 429 with an unknown code, as a plain rate limit', { detail: 'Too many summary requests. Try again shortly.', code: 'quota_v9' }, {}, 60],
    ['a 429 carrying the plan code, registered on 403, as a plain rate limit',
      { detail: 'Too many summary requests. Try again shortly.', code: 'plan_required' }, {}, 60],
  ])('gives %s on a 429 the wait it lifts after', async (_, body, headers, wait) => {
    const { calls } = await refusedOnHttp(429, body, headers)
    expect(calls).toHaveLength(1)
    // Pro's monthly cap lifts when the month turns, never in a minute, unless the server states a wait; a plain 429
    // keeps its moment's wait.
    expect(calls[0][1]?.retryAfterSeconds).toBe(wait)
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

