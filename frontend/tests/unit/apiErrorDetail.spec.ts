import { readFileSync } from 'node:fs'
import path from 'node:path'
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import ts from 'typescript'
import { afterEach, describe, expect, it } from 'vitest'
import api, { ApiError, detailMessage } from '@/lib/api/client'

/**
 * CAL-12 and the 422 gap: the messages lib/api/client.ts makes for the UI are sentences a reader can act
 * on. A failed connection used to read "Unable to connect to the server. Please ensure the backend API is
 * running on https://api.earningsnerd.io" (in the alert bell's popover, among others): a developer
 * instruction with the API's URL. FastAPI's validation 422 sends `detail` as a list of { loc, msg, type },
 * which reached the UI as "[object Object]".
 *
 * Holds: a network failure yields the plain sentence, with no URL; a 422 list detail yields its first msg;
 * a string detail is passed through as the backend wrote it; and no message literal in client.ts (every
 * value assigned to `errorMessage`, every argument to `new ApiError`) names the backend, a URL or the API
 * address helper. getApiUrl's own URLs are configuration, not messages, and are not read.
 */

const CLIENT = path.resolve(__dirname, '../../lib/api/client.ts')
const original = api.defaults.adapter

function failWith(make: (config: InternalAxiosRequestConfig) => AxiosError) {
  const adapter: AxiosAdapter = (config) => Promise.reject(make(config))
  api.defaults.adapter = adapter
}

async function caught(): Promise<ApiError> {
  try {
    await api.get('/api/watchlist/')
  } catch (err) {
    return err as ApiError
  }
  throw new Error('the request did not fail')
}

describe('client.ts error messages (CAL-12, 422 detail)', () => {
  afterEach(() => {
    api.defaults.adapter = original
  })

  it('a network failure yields a plain sentence with no URL or developer instruction', async () => {
    failWith((config) => new AxiosError('Network Error', AxiosError.ERR_NETWORK, config))
    const err = await caught()
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(0)
    expect(err.detail).toBe('Could not reach the server. Try again in a moment.')
  })

  it('a 422 list detail yields its first msg, never "[object Object]"', async () => {
    failWith((config) => {
      const response = {
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config,
        data: { detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' }, { loc: ['body', 'name'], msg: 'Field required', type: 'missing' }] },
      }
      return new AxiosError('Request failed with status code 422', AxiosError.ERR_BAD_REQUEST, config, null, response)
    })
    const err = await caught()
    expect(err.status).toBe(422)
    expect(err.detail).toBe('value is not a valid email address')
  })

  it('detailMessage keeps a string, flattens a list or object to its msg, and leaves anything else to the status', () => {
    expect(detailMessage('Watchlist is full.')).toBe('Watchlist is full.')
    expect(detailMessage([{ msg: 'Field required' }])).toBe('Field required')
    expect(detailMessage({ msg: 'Field required' })).toBe('Field required')
    expect(detailMessage([{ loc: ['body'] }])).toBeUndefined()
    expect(detailMessage([])).toBeUndefined()
    expect(detailMessage('')).toBeUndefined()
    expect(detailMessage(undefined)).toBeUndefined()
    expect(detailMessage({ code: 'quota' })).toBeUndefined()
  })

  it("detailMessage drops pydantic's prefix from a custom validator's msg, and only at the start", () => {
    // A field_validator that raises ValueError reaches the client as "Value error, <its sentence>", an
    // assert as "Assertion failed, <its sentence>": the reader sees the validator's sentence alone.
    expect(detailMessage([{ msg: 'Value error, Tickers are letters only.', type: 'value_error' }, { msg: 'Field required' }])).toBe('Tickers are letters only.')
    expect(detailMessage([{ msg: 'Assertion failed, Pick at least one filing.', type: 'assertion_error' }])).toBe('Pick at least one filing.')
    expect(detailMessage({ msg: 'Value error, Tickers are letters only.' })).toBe('Tickers are letters only.')
    // Not a prefix: left as the backend wrote it. A string detail is never rewritten.
    expect(detailMessage([{ msg: 'Expected a value error, got none' }])).toBe('Expected a value error, got none')
    expect(detailMessage([{ msg: 'Value error,' }])).toBe('Value error,')
    expect(detailMessage([{ msg: 'Value error, ' }])).toBe('Value error, ')
    expect(detailMessage('Value error, kept as sent')).toBe('Value error, kept as sent')
  })

  it('no message literal in client.ts names the backend, a URL or the API address', () => {
    const text = readFileSync(CLIENT, 'utf8')
    const sf = ts.createSourceFile(CLIENT, text, ts.ScriptTarget.Latest, true)
    const messages: { line: number; text: string }[] = []
    // The literals a message is made of: string literals and whole template literals (with their
    // substitutions), anywhere in the assigned expression (`error.message || 'An unexpected …'`).
    const take = (expr: ts.Node): void => {
      if (ts.isStringLiteralLike(expr) || ts.isTemplateExpression(expr)) {
        messages.push({ line: sf.getLineAndCharacterOfPosition(expr.getStart(sf)).line + 1, text: expr.getText(sf) })
        return
      }
      ts.forEachChild(expr, take)
    }
    const visit = (node: ts.Node): void => {
      if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && node.left.getText(sf) === 'errorMessage') take(node.right)
      if (ts.isNewExpression(node) && node.expression.getText(sf) === 'ApiError') for (const arg of node.arguments ?? []) take(arg)
      ts.forEachChild(node, visit)
    }
    visit(sf)
    // Anti-vacuity: the status chain's seven messages are all read (503, 429, 404, 5xx, network, timeout, other).
    expect(messages.length).toBeGreaterThanOrEqual(7)
    expect(messages.filter((m) => /backend|https?:\/\/|getApiUrl|localhost/i.test(m.text)).map((m) => `client.ts:${m.line} ${m.text}`)).toEqual([])
  })
})
