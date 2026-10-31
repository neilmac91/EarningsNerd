import { AxiosError, AxiosHeaders, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import api, { ApiError, EMAIL_VERIFICATION_REQUIRED_EVENT, parseErrorCode } from '@/lib/api/client'

/**
 * ApiError.backendDetail tells the backend's own words from lib/api/client's. `detail` is always a
 * sentence (the backend's, else a status fallback or axios's message), so a surface that shows backend
 * text verbatim (the full-text search alert) reads `backendDetail`, set only when the response body
 * carried a readable string `detail`.
 */

const original = api.defaults.adapter

function respondWith(status: number, data: unknown) {
  const adapter: AxiosAdapter = (config: InternalAxiosRequestConfig) => {
    const response = { status, statusText: '', data, headers: new AxiosHeaders(), config }
    return Promise.reject(new AxiosError(`Request failed with status code ${status}`, AxiosError.ERR_BAD_RESPONSE, config, null, response))
  }
  api.defaults.adapter = adapter
}

async function caught(): Promise<ApiError> {
  try {
    await api.get('/api/search/full-text')
  } catch (err) {
    return err as ApiError
  }
  throw new Error('the request did not fail')
}

describe('ApiError.backendDetail', () => {
  afterEach(() => {
    api.defaults.adapter = original
  })

  it('carries a string detail from the response body', async () => {
    respondWith(502, { detail: 'SEC full-text search is temporarily unavailable.' })
    const err = await caught()
    expect(err).toBeInstanceOf(ApiError)
    expect(err.backendDetail).toBe('SEC full-text search is temporarily unavailable.')
    expect(err.detail).toBe('SEC full-text search is temporarily unavailable.')
  })

  it.each([
    ['a 502 HTML gateway page', 502, '<html>Bad Gateway</html>', 'A server error occurred. Please try again later.'],
    ['a 413 with no detail', 413, {}, 'Request failed with status code 413'],
    ['a bodiless 503', 503, '', 'Service temporarily unavailable. Please try again in a moment.'],
    ['an empty detail', 429, { detail: '' }, 'Too many requests. Please wait a moment before trying again.'],
  ])('is undefined for %s, where detail is the client fallback', async (_name, status, data, detail) => {
    respondWith(status, data)
    const err = await caught()
    expect(err.backendDetail).toBeUndefined()
    expect(err.detail).toBe(detail)
  })

  // FastAPI's validation 422 carries a list in `detail`, not a sentence; detailMessage() reads the list's first `msg`,
  // so backendDetail carries that sentence.
  it("carries a FastAPI validation list's first msg (a 422), read by detailMessage()", async () => {
    respondWith(422, { detail: [{ loc: ['body', 'q'], msg: 'x', type: 'value_error' }] })
    const err = await caught()
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(422)
    expect(err.backendDetail).toBe('x')
  })
})

/**
 * ApiError.code (E31, docs/audit/contracts/error-codes.md): a body's `code` is kept only when this client knows it and
 * it arrived on its registered status, so an older server (no code), a newer one (a code this client does not know)
 * and a mismatched status all leave the status and the words to decide, as before codes existed.
 */
describe('ApiError.code', () => {
  afterEach(() => {
    api.defaults.adapter = original
  })

  it.each([
    ['a known code on its status', 403, { detail: 'Words.', code: 'plan_required' }, 'plan_required'],
    ['no code (an older server)', 403, { detail: 'Words.' }, undefined],
    ['a code this client does not know (a newer server)', 403, { detail: 'Words.', code: 'brand_new_code' }, undefined],
    ['a known code on another status', 500, { detail: 'Words.', code: 'plan_required' }, undefined],
    ['a code that is not a string', 403, { detail: 'Words.', code: ['plan_required'] }, undefined],
    ["a key of Object's prototype", 403, { detail: 'Words.', code: 'toString' }, undefined],
  ])('reads %s', async (_name, status, data, code) => {
    respondWith(status, data)
    const err = await caught()
    expect(err.code).toBe(code)
    // The code changes nothing else the error carries.
    expect(err.status).toBe(status)
    expect(err.backendDetail).toBe('Words.')
    expect(err.isRetryable).toBe(status >= 500)
  })

  it("never honours a key that reaches ERROR_CODES only through Object's prototype", () => {
    // A polluted prototype member shaped like a registered code must still read as no code.
    const proto = Object.prototype as Record<string, unknown>
    proto.polluted_code = { status: 403, stream: true }
    try {
      expect(parseErrorCode('polluted_code', 403)).toBeUndefined()
      expect(parseErrorCode('polluted_code', 'stream')).toBeUndefined()
    } finally {
      delete proto.polluted_code
    }
  })

  it('honours a stream code only on a stream, and an HTTP-only code never there', () => {
    expect(parseErrorCode('free_allowance_exhausted', 'stream')).toBe('free_allowance_exhausted')
    expect(parseErrorCode('pro_fair_use_limit', 'stream')).toBe('pro_fair_use_limit')
    expect(parseErrorCode('generation_paused', 'stream')).toBe('generation_paused')
    expect(parseErrorCode('email_verification_required', 'stream')).toBeUndefined()
    expect(parseErrorCode('pro_fair_use_limit', 429)).toBe('pro_fair_use_limit')
    expect(parseErrorCode('pro_fair_use_limit', 403)).toBeUndefined()
  })
})

describe('the email-verification prompt', () => {
  afterEach(() => {
    api.defaults.adapter = original
  })

  async function prompted(status: number, data: unknown): Promise<boolean> {
    const listener = vi.fn()
    window.addEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, listener)
    try {
      respondWith(status, data)
      await caught()
    } finally {
      window.removeEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, listener)
    }
    return listener.mock.calls.length === 1
  }

  it('opens on the code, whatever the words say', async () => {
    expect(await prompted(403, { detail: 'Confirm your inbox first.', code: 'email_verification_required' })).toBe(true)
  })

  it('opens on the words when there is no code (an older server)', async () => {
    expect(await prompted(403, { detail: 'Verify your email address before you subscribe.' })).toBe(true)
  })

  it('stays shut when a known code says it is another refusal, whatever the words say', async () => {
    expect(await prompted(403, { detail: 'Verify your email to unlock Pro.', code: 'plan_required' })).toBe(false)
  })

  it('falls back to the words for a code this client does not know', async () => {
    expect(await prompted(403, { detail: 'Verify your email address before you subscribe.', code: 'brand_new_code' })).toBe(true)
  })
})
