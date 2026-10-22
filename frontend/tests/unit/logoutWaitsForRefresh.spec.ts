import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'

// The refresh is mocked so each case decides when, and how, the refresh in flight answers.
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))

import api, { ensureRefreshed } from '@/lib/api/client'
import { refreshAccessToken } from '@/lib/api/refresh'
import { LOGOUT_REFRESH_WAIT_MS, LogoutAllSuperseded, getCurrentUser, logout, logoutAllSessions } from '@/features/auth/api/auth-api'
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

  it('waits no longer than the limit for a refresh that never answers, and cancels it before it posts', async () => {
    vi.useFakeTimers()
    refreshInFlight()
    const signal = refreshMock.mock.calls[0][1] as AbortSignal
    const loggingOut = logout()
    await vi.advanceTimersByTimeAsync(LOGOUT_REFRESH_WAIT_MS - 1)
    expect(events).toEqual([])
    expect(signal.aborted).toBe(false)

    // Cancelled, the refresh's answer is dropped, its cookies with it, so it cannot land after the logout's.
    await vi.advanceTimersByTimeAsync(1)
    expect(signal.aborted).toBe(true)
    await loggingOut
    expect(events).toEqual(['post /api/auth/logout'])
  })

  it('cancels nothing that answered within the limit', async () => {
    const { answer, refreshing } = refreshInFlight()
    const signal = refreshMock.mock.calls[0][1] as AbortSignal
    const loggingOut = logout()
    await settle()
    answer.resolve()
    await refreshing
    await loggingOut
    expect(signal.aborted).toBe(false)
  })

  it('marks nothing active from a /me read while it is under way, so a later 401 starts no refresh', async () => {
    // A request sent while the session was active, answered 401 only after the logout has started; and the logout's
    // own answer, held so the /me read and that 401 both land while it is under way.
    const earlier = deferred<void>()
    const logoutAnswer = deferred<void>()
    api.defaults.adapter = async (config) => {
      events.push(`${config.method} ${config.url}`)
      if (config.url === '/api/filings/1') {
        await earlier.promise
        throw unauthorized(config)
      }
      if (config.url === '/api/auth/logout') await logoutAnswer.promise
      return ok(config)
    }
    const sentBefore = api.get('/api/filings/1').catch((error: unknown) => error)
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logout()
    await settle()
    answer.resolve()
    await refreshing
    await settle()
    expect(events).toEqual(['get /api/filings/1', 'refresh answered', 'post /api/auth/logout'])

    // The refresh succeeded, so a /me it replays is answered: it must not mark the session active again, here or in
    // the storage other tabs read, where a marker would let another tab start a refresh whose cookies outlast the
    // logout's for the whole browser.
    await getCurrentUser()
    expect(hasActiveSession()).toBe(false)
    expect(window.localStorage.getItem('en_session_active')).toBeNull()
    earlier.resolve()
    await expect(sentBefore).resolves.toMatchObject({ status: 401 })
    expect(refreshMock).toHaveBeenCalledTimes(1)

    logoutAnswer.resolve()
    await loggingOut
    expect(hasActiveSession()).toBe(false)
  })

  it('lets no other tab\'s marker arm a refresh while it is under way', async () => {
    const logoutAnswer = deferred<void>()
    api.defaults.adapter = async (config) => {
      events.push(`${config.method} ${config.url}`)
      if (config.url === '/api/auth/logout') {
        await logoutAnswer.promise
        return ok(config)
      }
      throw unauthorized(config) // the access token has expired
    }
    const loggingOut = logout()
    await settle()

    // Another tab of this browser marks the session active in the storage both tabs read.
    window.localStorage.setItem('en_session_active', '1')
    expect(hasActiveSession()).toBe(false)
    await expect(api.get('/api/filings/1')).rejects.toMatchObject({ status: 401 })
    expect(refreshMock).not.toHaveBeenCalled()

    logoutAnswer.resolve()
    await loggingOut
  })

  it('keeps the session inactive until the last of two logouts under way has settled', async () => {
    const answers = { '/api/auth/logout': deferred<void>(), '/api/auth/logout-all': deferred<void>() }
    api.defaults.adapter = async (config) => {
      events.push(`${config.method} ${config.url}`)
      await answers[config.url as keyof typeof answers]?.promise
      return ok(config)
    }
    const one = logout()
    const all = logoutAllSessions()
    await settle()
    answers['/api/auth/logout'].resolve()
    await one

    // The other logout is still under way: a /me answered now marks nothing.
    await getCurrentUser()
    expect(hasActiveSession()).toBe(false)
    answers['/api/auth/logout-all'].resolve()
    await all
    await getCurrentUser()
    expect(hasActiveSession()).toBe(true)
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

    // A login completes and is accepted meanwhile: it marks the session and starts a new explicit generation. That
    // account's session is live at once, though the earlier logout still waits.
    markSessionActive()
    advanceSessionGeneration('explicit')
    expect(hasActiveSession()).toBe(true)
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

  it('refuses to post for a login accepted while it waited, and leaves that login signed in', async () => {
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logoutAllSessions()
    const outcome = loggingOut.catch((error: unknown) => error)
    await settle()

    // Another account logs in and is accepted meanwhile; its cookies are the ones a post would now carry, and the
    // server ends every session of the account a request carries.
    markSessionActive()
    advanceSessionGeneration('explicit')
    answer.resolve()
    await refreshing
    expect(await outcome).toBeInstanceOf(LogoutAllSuperseded)
    expect(events).toEqual(['refresh answered'])
    expect(hasActiveSession()).toBe(true)
  })

  it('still posts after a passive loss of the session during its wait', async () => {
    const { answer, refreshing } = refreshInFlight()
    const loggingOut = logoutAllSessions()
    await settle()

    // Another request's 401 confirms the session lost meanwhile: a new generation, but no explicit transition.
    advanceSessionGeneration('session-loss')
    answer.resolve()
    await refreshing
    await loggingOut
    expect(events).toEqual(['refresh answered', 'post /api/auth/logout-all'])
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
