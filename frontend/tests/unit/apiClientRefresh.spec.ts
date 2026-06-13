import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'

// Mock the refresh call so no real network request is made; the interceptor under test
// orchestrates *when* it fires and what happens after.
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))

import api, { ApiError, isRefreshableRequest } from '@/lib/api/client'
import { refreshAccessToken } from '@/lib/api/refresh'
import { markSessionActive, clearSessionActive, hasActiveSession } from '@/lib/api/session'

const refreshMock = refreshAccessToken as unknown as Mock

// Simulated server state: false => access token expired (401), true => valid (200).
let serverTokenValid = false

function makeResponse(config: any) {
  return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
}

function make401(config: any) {
  const err: any = new Error('Request failed with status code 401')
  err.config = config
  err.response = { status: 401, data: { detail: 'Token expired' }, headers: {}, config }
  err.isAxiosError = true
  return err
}

// Custom adapter: rejects with 401 until the (mocked) refresh marks the token valid.
const adapter = vi.fn(async (config: any) => {
  if (!serverTokenValid) {
    throw make401(config)
  }
  return makeResponse(config)
})

beforeEach(() => {
  serverTokenValid = false
  refreshMock.mockReset()
  adapter.mockClear()
  clearSessionActive()
  // A successful refresh flips the simulated server token to valid.
  refreshMock.mockImplementation(async () => {
    serverTokenValid = true
  })
  api.defaults.adapter = adapter as any
})

describe('isRefreshableRequest', () => {
  it('excludes the auth credential/refresh endpoints', () => {
    expect(isRefreshableRequest('/api/auth/refresh')).toBe(false)
    expect(isRefreshableRequest('/api/auth/login')).toBe(false)
    expect(isRefreshableRequest('/api/auth/register')).toBe(false)
    expect(isRefreshableRequest('/api/auth/logout')).toBe(false)
  })

  it('includes ordinary protected endpoints (and missing urls)', () => {
    expect(isRefreshableRequest('/api/auth/me')).toBe(true)
    expect(isRefreshableRequest('/api/filings/123')).toBe(true)
    expect(isRefreshableRequest(undefined)).toBe(true)
  })
})

describe('session flag', () => {
  it('marks, reads, and clears the active session', () => {
    expect(hasActiveSession()).toBe(false)
    markSessionActive()
    expect(hasActiveSession()).toBe(true)
    clearSessionActive()
    expect(hasActiveSession()).toBe(false)
  })
})

describe('silent refresh interceptor', () => {
  it('refreshes once and replays the request on a 401 for a logged-in user', async () => {
    markSessionActive()

    const res = await api.get('/api/filings/123')

    expect(res.status).toBe(200)
    expect(refreshMock).toHaveBeenCalledTimes(1)
    // Original 401 + replay after refresh.
    expect(adapter).toHaveBeenCalledTimes(2)
    expect(hasActiveSession()).toBe(true)
  })

  it('does not attempt a refresh for guests (no active session)', async () => {
    // No markSessionActive() — this is a guest.
    await expect(api.get('/api/auth/me')).rejects.toMatchObject({
      status: 401,
    })
    expect(refreshMock).not.toHaveBeenCalled()
  })

  it('coalesces concurrent 401s into a single refresh', async () => {
    markSessionActive()
    // A real (short) async refresh so all three 401s are in flight and queue behind the
    // single shared refresh promise before it resolves.
    refreshMock.mockImplementation(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10))
      serverTokenValid = true
    })

    const results = await Promise.all([
      api.get('/api/filings/1'),
      api.get('/api/filings/2'),
      api.get('/api/filings/3'),
    ])

    expect(results.every((r) => r.status === 200)).toBe(true)
    expect(refreshMock).toHaveBeenCalledTimes(1)
  })

  it('clears the session and surfaces the 401 when refresh fails', async () => {
    markSessionActive()
    refreshMock.mockRejectedValue(new Error('refresh rejected'))

    await expect(api.get('/api/filings/123')).rejects.toBeInstanceOf(ApiError)
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(hasActiveSession()).toBe(false)
  })

  it('retries only once — a persistent 401 is not refreshed in a loop', async () => {
    markSessionActive()
    // Refresh "succeeds" but the server keeps 401ing (e.g. token still rejected).
    refreshMock.mockResolvedValue(undefined) // does NOT flip serverTokenValid

    await expect(api.get('/api/filings/123')).rejects.toMatchObject({ status: 401 })
    // Exactly one refresh, and the request was attempted twice (original + single replay).
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('propagates a non-401 error from the replayed request and keeps the session', async () => {
    // Regression: the replay must run outside the refresh try/catch, so a 500 (or 429) from
    // the *retried* request surfaces as itself — not swallowed and reported as the original 401,
    // and without wrongly clearing a still-valid session.
    markSessionActive()
    let call = 0
    api.defaults.adapter = vi.fn(async (config: any) => {
      call += 1
      if (call === 1) throw make401(config) // access token expired
      // Refresh succeeded; the replayed request then hits a real server error.
      const err: any = new Error('Request failed with status code 500')
      err.config = config
      err.response = { status: 500, data: { detail: 'boom' }, headers: {}, config }
      err.isAxiosError = true
      throw err
    }) as any
    refreshMock.mockResolvedValue(undefined)

    await expect(api.get('/api/filings/123')).rejects.toMatchObject({ status: 500 })
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(hasActiveSession()).toBe(true) // valid session must NOT be cleared
  })

  it('falls back to the in-memory flag when localStorage is unavailable', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('localStorage blocked')
    })
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('localStorage blocked')
    })
    try {
      // Even though storage throws, marking then reading the session works in-memory, so a
      // logged-in user in Safari private mode still gets silent refresh.
      markSessionActive()
      expect(hasActiveSession()).toBe(true)

      const res = await api.get('/api/filings/9')
      expect(res.status).toBe(200)
      expect(refreshMock).toHaveBeenCalledTimes(1)
    } finally {
      getItem.mockRestore()
      setItem.mockRestore()
    }
  })
})
