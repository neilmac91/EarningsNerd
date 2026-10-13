import { AxiosError, AxiosHeaders, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import api, { ApiError } from '@/lib/api/client'

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
    ['an empty detail', 429, { detail: '' }, 'Too many requests. Please wait a moment before trying again.'],
  ])('is undefined for %s, where detail is the client fallback', async (_name, status, data, detail) => {
    respondWith(status, data)
    const err = await caught()
    expect(err.backendDetail).toBeUndefined()
    expect(err.detail).toBe(detail)
  })
})
