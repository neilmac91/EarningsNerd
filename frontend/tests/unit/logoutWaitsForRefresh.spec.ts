import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'

// The refresh is mocked so each case decides when, and how, the refresh in flight answers.
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))

import api, { ensureRefreshed } from '@/lib/api/client'
import { refreshAccessToken } from '@/lib/api/refresh'
import { LOGOUT_REFRESH_WAIT_MS, logout, logoutAllSessions } from '@/features/auth/api/auth-api'
import { advanceSessionGeneration, clearSessionActive, hasActiveSession, markSessionActive } from '@/lib/api/session'

/**
 * A silent refresh answers with the session cookies. One that answers after a logout's answer sets them again, the
 * access token among them, which nothing revokes, so the tab stays signed in until it expires (E133). A logout
 * therefore starts no new refresh, lets the one in flight answer first, and only then posts.
 */

const refreshMock = vi.mocked(refreshAccessToken)
const originalAdapter = api.defaults.adapter
// What reached the server, in order: each request, and each refresh's answer.
const events: string[] = []
// Each case's refresh in flight, answered after the case so that none outlives it in the client's module state.
const inFlight: { answer: { resolve: (value: void) => void }; refreshing: Promise<unknown> }[] = []

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const ok = (config: InternalAxiosRequestConfig) => ({ data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config })
const unauthorized = (config: InternalAxiosRequestConfig) => Object.assign(new Error('Request failed with status code 401'), {
  config, isAxiosError: true, response: { status: 401, statusText: 'Unauthorized', data: { detail: 'Token expired' }, headers: {}, config },
})
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

/** A refresh in flight that answers when the case says so. */
function refreshInFlight() {
  const answer = deferred<void>()
  refreshMock.mockImplementation(() => answer.promise.then(() => { events.push('refresh answered') }))
  const refreshing = ensureRefreshed().catch(() => 'failed')
  inFlight.push({ answer, refreshing })
  return { answer, refreshing }
}

beforeEach(() => {
  events.length = 0
  refreshMock.mockReset()
  clearSessionActive()
  markSessionActive()
  api.defaults.adapter = async (config) => {
    events.push(`${config.method} ${config.url}`)
    return ok(config)
  }
})

afterEach(async () => {
  vi.useRealTimers()
  for (const { answer, refreshing } of inFlight.splice(0)) {
    answer.resolve()
    await refreshing
  }
  api.defaults.adapter = originalAdapter
})

describe('a logout waits for the refresh in flight', () => {
  it('posts only after the refresh in flight has answered', async () => {
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logout()
    await settle()
    expect(events).toEqual([])

    answer.resolve()
    await refreshing
    await loggingOut
    expect(events).toEqual(['refresh answered', 'post /api/auth/logout'])
    expect(hasActiveSession()).toBe(false)
  })

  it('still posts when the refresh in flight fails', async () => {
    const answer = deferred<void>()
    refreshMock.mockImplementation(() => answer.promise)
    const refreshing = ensureRefreshed().catch(() => 'failed')
    inFlight.push({ answer, refreshing })
    const loggingOut = logout()
    await settle()
    expect(events).toEqual([])

    answer.reject(new Error('Network Error'))
    expect(await refreshing).toBe('failed')
    await loggingOut
    expect(events).toEqual(['post /api/auth/logout'])
  })

  it('waits no longer than the limit for a refresh that never answers', async () => {
    vi.useFakeTimers()
    refreshInFlight()
    const loggingOut = logout()
    await vi.advanceTimersByTimeAsync(LOGOUT_REFRESH_WAIT_MS - 1)
    expect(events).toEqual([])

    await vi.advanceTimersByTimeAsync(1)
    await loggingOut
    expect(events).toEqual(['post /api/auth/logout'])
  })

  it('posts at once when no refresh is in flight', async () => {
    vi.useFakeTimers() // a wait on the limit would never end here
    await logout()
    expect(events).toEqual(['post /api/auth/logout'])
    expect(refreshMock).not.toHaveBeenCalled()
  })

  it('leaves a login accepted while it waited signed in', async () => {
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logout()
    await settle()

    // A login completes and is accepted meanwhile: it marks the session and starts a new explicit generation.
    markSessionActive()
    advanceSessionGeneration('explicit')
    answer.resolve()
    await refreshing
    await loggingOut
    expect(events).toEqual(['refresh answered'])
    expect(hasActiveSession()).toBe(true)
  })

  it('still posts after a passive loss of the session during its wait', async () => {
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logout()
    await settle()

    // Another request's 401 confirms the session lost meanwhile: a new generation, but no explicit transition.
    advanceSessionGeneration('session-loss')
    answer.resolve()
    await refreshing
    await loggingOut
    expect(events).toEqual(['refresh answered', 'post /api/auth/logout'])
  })

  it('starts no refresh for a newer account that was waiting out an earlier one', async () => {
    // An earlier account's refresh is in flight; the account now signed in waits it out to refresh its own.
    const { answer, refreshing } = refreshInFlight()
    advanceSessionGeneration('explicit')
    markSessionActive()
    const chained = ensureRefreshed().catch((error: unknown) => error)
    const loggingOut = logout()
    await settle()

    answer.resolve()
    await refreshing
    expect(await chained).toMatchObject({ name: 'AbortError' })
    await loggingOut
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(events).toEqual(['refresh answered', 'post /api/auth/logout'])
  })
})

describe('a logout of every session waits for the refresh in flight', () => {
  it('posts only after the refresh in flight has answered', async () => {
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logoutAllSessions()
    await settle()
    expect(events).toEqual([])

    answer.resolve()
    await refreshing
    await loggingOut
    expect(events).toEqual(['refresh answered', 'post /api/auth/logout-all'])
    expect(hasActiveSession()).toBe(false)
  })
})

describe.each([
  ['a logout', logout, '/api/auth/logout'],
  ['a logout of every session', logoutAllSessions, '/api/auth/logout-all'],
])('%s', (_, logOut, path) => {
  it('starts no new refresh while it is under way', async () => {
    const logoutAnswer = deferred<void>()
    refreshMock.mockResolvedValue(undefined)
    api.defaults.adapter = async (config) => {
      events.push(`${config.method} ${config.url}`)
      if (config.url === path) {
        await logoutAnswer.promise
        return ok(config)
      }
      throw unauthorized(config) // the access token has expired
    }
    const loggingOut = logOut()
    await settle()
    expect(events).toEqual([`post ${path}`])

    // A request whose access token expired while the logout is in flight: its 401 must not start a refresh.
    await expect(api.get('/api/filings/1')).rejects.toMatchObject({ status: 401 })
    expect(refreshMock).not.toHaveBeenCalled()

    logoutAnswer.resolve()
    await loggingOut
  })
})
