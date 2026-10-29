import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import api from '@/lib/api/client'
import { LogoutAllSuperseded, logout, type CurrentUser } from '@/features/auth/api/auth-api'
import {
  LOGGED_OUT_FIRST_MESSAGE, LOGOUT_FAILED_MESSAGE, LoggedOutFirst, acceptLoginAndResetAccount, logoutAllInTurn, logoutAndResetAccount,
  subscribeAccountQueryReset,
} from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getExplicitSessionGeneration, hasActiveSession, markSessionActive } from '@/lib/api/session'
import { refreshAccessToken } from '@/lib/api/refresh'
import { queryKeys } from '@/lib/queryKeys'
import { QUERY_CLIENT_DEFAULTS } from '@/app/providers'
import Header from '@/components/Header'
import SettingsPage from '@/app/dashboard/settings/page'
import { LOGOUT_ALL_CALL_SITES } from './logoutCallSites'

/**
 * The settings page's "Log out of all devices" runs in the one-logout flight the Log out controls share (E157;
 * logoutAllInTurn, features/auth/lib/accountQueryState.ts). Pressed while a Log out runs, it waits for that one. When
 * the Log out did not take (its request failed and /me still names the same reader, or could not be read), it posts.
 * When the Log out took, this device has no session left to end the others with: it posts nothing and says so, in a
 * toast, since the page leaves with that Log out. When a login overtook the Log out, or its /me named another reader
 * (another tab signed in), it posts nothing and says nothing. A Log out pressed while it runs waits for it: settled
 * with it when it took, and logging out on its own when it failed. One that failed puts the session flag back, so a
 * lapsed access cookie still renews. Beside the flight, before E157, its `beginLogout` cleared the session flag a failed
 * Log out's read of /me needs, so a lapsed access cookie read as a guest and that Log out left as logged out with the
 * refresh cookie alive (#1496's review), and a Log out's reset lifted its refresh fence or ended it as superseded.
 *
 * The page renders under the site header, as the app renders it, its other sections aside, in a client built as
 * Providers builds the app's; the requests run through the real API client, auth API and flight, with the adapter
 * answering, so the session flag, the generation fences and the page's guard are the ones the app runs. The refresh is
 * the one stub.
 */

const nav = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn(), back: vi.fn(), forward: vi.fn(), prefetch: vi.fn() }))
const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), warning: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => nav, usePathname: () => '/dashboard/settings' }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
vi.mock('sonner', () => ({ toast: toasts }))
vi.mock('@/lib/analytics', () => ({ default: { identify: vi.fn(), logout: vi.fn() } }))
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))
// The header's chrome and the page's other sections are not under test.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/features/notifications/components/NotificationBell', () => ({ default: () => null }))
vi.mock('@/features/settings/components/ProfileForm', () => ({ default: () => null }))
vi.mock('@/features/settings/components/BillingPanel', () => ({ default: () => null }))
vi.mock('@/features/settings/components/ChangePasswordForm', () => ({ default: () => null }))
vi.mock('@/features/settings/components/NotificationPreferencesForm', () => ({ default: () => null }))

const reader: CurrentUser = {
  id: 7, email: 'reader@example.com', full_name: 'Reader', is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}
const other: CurrentUser = { ...reader, id: 8, email: 'other@example.com', full_name: 'Other' }

type Answer = (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>
const ok = (data: unknown): Answer => async (config) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const status = (code: number, detail: string): Answer => async (config) => {
  throw Object.assign(new Error(`Request failed with status code ${code}`), { config, response: { status: code, data: { detail } } })
}
const unreachable: Answer = async (config) => { throw Object.assign(new Error('Network Error'), { config }) }
/** An answer held until the case lets it go. */
const heldUntil = (gate: Promise<void>, answer: Answer): Answer => async (config) => { await gate; return answer(config) }
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}
/** Let pending fetches, renders and effects run. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

const LOGOUT_INCOMPLETE = 'This browser is logged out, but we could not end the session on the server.'
const refused = async (): Promise<void> => { throw { response: { status: 401 } } }
/** This browser's cookies cleared: /me then answers no user, the refresh cookie is gone, and so is the logout of every
    session, whose route needs the access cookie (`get_current_user`). */
const cookiesCleared = () => {
  Object.assign(server, { me: status(401, 'Not authenticated'), logoutAll: status(401, 'Not authenticated'), refresh: refused, renewed: false })
}
/** A logout that took. */
const endsThisSession: Answer = async (config) => {
  cookiesCleared()
  return ok({ status: 'success' })(config)
}
/** The logout route's 503: it cleared this browser's cookies, but could not end the session on the server. */
const incomplete: Answer = async (config) => {
  cookiesCleared()
  return status(503, LOGOUT_INCOMPLETE)(config)
}
/** A logout of every session that took: this browser's session ends with the others. */
const endsEverySession: Answer = async (config) => {
  Object.assign(server, { me: status(401, 'Not authenticated'), refresh: refused, renewed: false })
  return ok({ status: 'success', sessions_revoked: 3 })(config)
}
/** What the API answers: /me, the two logouts and the refresh, each replaceable mid-test; every request is recorded. */
const server = {
  me: ok(reader),
  logout: endsThisSession,
  logoutAll: endsEverySession,
  /** The refresh cookie: refused unless a case renews the session. */
  refresh: refused,
  renewed: false,
  requests: [] as string[],
}
const renews = async () => { server.renewed = true }
/** The access cookie has lapsed: /me answers 401 until the refresh renews the session. */
const lapsed: Answer = (config) => (server.renewed ? ok(reader) : status(401, 'Could not validate credentials'))(config)
const posts = (path: string) => server.requests.filter((request) => request === `post ${path}`).length
const meReads = () => server.requests.filter((request) => request === 'get /api/auth/me').length
const originalAdapter = api.defaults.adapter
const clients: QueryClient[] = []
const disposers: (() => void)[] = []

beforeEach(() => {
  // A flight a failed case left behind answers for an earlier generation, so no press here joins it.
  advanceSessionGeneration()
  clearSessionActive()
  Object.assign(server, { me: ok(reader), logout: endsThisSession, logoutAll: endsEverySession, refresh: refused, renewed: false, requests: [] })
  vi.mocked(refreshAccessToken).mockImplementation(() => server.refresh())
  api.defaults.adapter = async (config) => {
    server.requests.push(`${config.method} ${config.url}`)
    if (config.url === '/api/auth/me') return server.me(config)
    if (config.url === '/api/auth/logout') return server.logout(config)
    if (config.url === '/api/auth/logout-all') return server.logoutAll(config)
    if (config.url === '/api/auth/connections') return ok({ has_password: true, providers: [] })(config)
    throw new Error(`unexpected request ${config.method} ${config.url}`)
  }
})
afterEach(() => {
  cleanup()
  disposers.splice(0).forEach((dispose) => dispose())
  clients.splice(0).forEach((client) => client.clear())
  api.defaults.adapter = originalAdapter
  vi.clearAllMocks()
})

/** A client as Providers builds the app's: its defaults, and the account reset when a request confirms the session lost. */
const newClient = () => {
  const client = new QueryClient({ defaultOptions: QUERY_CLIENT_DEFAULTS })
  clients.push(client)
  disposers.push(subscribeAccountQueryReset(client))
  return client
}
/** The settings page under the site header, once both have read the reader, with the client and a watch on its clear(),
    which only a logout of every session that took calls (ConnectedAccounts). */
async function renderSettings() {
  const client = newClient()
  const clear = vi.spyOn(client, 'clear')
  render(<QueryClientProvider client={client}><Header /><SettingsPage /></QueryClientProvider>)
  await screen.findByRole('button', { name: 'Account menu' })
  await screen.findByRole('button', { name: 'Log out of all devices' })
  return { client, clear }
}
const everywhere = () => screen.getByRole('button', { name: 'Log out of all devices' })
/** The account menu's Log out. */
const logOut = () => {
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
  fireEvent.click(screen.getByRole('menuitem', { name: 'Log out' }))
}
/** Once the logout of every session has ended: its error, or null when it took (its control then clears the cache, and
    its mutation with it). */
const logoutAllEnded = async (client: QueryClient, clear: MockInstance) => {
  const ended = () => clear.mock.calls.length > 0 || client.getMutationCache().getAll().some(({ state }) => state.status === 'error')
  await waitFor(() => expect(ended()).toBe(true))
  return clear.mock.calls.length > 0 ? null : client.getMutationCache().getAll()[0].state.error
}

describe('the control whose cases run below', () => {
  it('is the one the gate inventories, so a new one gets its cases', () => {
    expect(Object.keys(LOGOUT_ALL_CALL_SITES)).toEqual(['features/settings/components/ConnectedAccounts.tsx'])
  })
})

describe('"Log out of all devices" pressed while a Log out runs', () => {
  it("waits while a failed Log out reads /me, leaving it the session flag, so a lapsed access cookie renews; then, the session alive, it logs every session out", async () => {
    const { clear } = await renderSettings()
    const read = deferred<void>()
    Object.assign(server, { logout: unreachable, me: heldUntil(read.promise, lapsed), refresh: renews })
    logOut()
    // The Log out's request failed, and its read of /me is out with the account still on screen.
    await waitFor(() => expect(meReads()).toBe(2))
    const button = await screen.findByRole('button', { name: 'Log out of all devices' })
    fireEvent.click(button)
    await settle()
    // It waits, busy, and the flag stays as the Log out put it back for its read: no beginLogout of its own clears it.
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(hasActiveSession()).toBe(true)
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    read.resolve()
    await waitFor(() => expect(clear).toHaveBeenCalledTimes(1))
    // /me's 401 was the lapsed access cookie: the refresh cookie renewed the session, /me named the reader, and the Log
    // out said it did not take. Only then did the logout of every session post, once, and leave for /login.
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGOUT_FAILED_MESSAGE)
    expect(server.requests.filter((request) => request !== 'get /api/auth/connections').slice(0, 5)).toEqual([
      'get /api/auth/me', 'post /api/auth/logout', 'get /api/auth/me', 'get /api/auth/me', 'post /api/auth/logout-all',
    ])
    expect(posts('/api/auth/logout-all')).toBe(1)
    expect(nav.push).toHaveBeenCalledWith('/login')
    expect(nav.push).not.toHaveBeenCalledWith('/')
  })

  it("pressed while a Log out's request is out, waits for that Log out to fail and its reset to move the generation, then, the session alive, logs every session out", async () => {
    const { clear } = await renderSettings()
    const answer = deferred<void>()
    server.logout = heldUntil(answer.promise, unreachable)
    logOut()
    await waitFor(() => expect(posts('/api/auth/logout')).toBe(1))
    fireEvent.click(everywhere())
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    // The request fails; the Log out's reset moves the generation the flight answers for, and /me names the reader.
    answer.resolve()
    await waitFor(() => expect(posts('/api/auth/logout-all')).toBe(1))
    await waitFor(() => expect(clear).toHaveBeenCalledTimes(1))
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGOUT_FAILED_MESSAGE)
    expect(nav.push).toHaveBeenCalledWith('/login')
    expect(nav.push).not.toHaveBeenCalledWith('/')
  })

  it('posts when the failed Log out it waited for could not read /me (a 500), which that Log out counts as not taken', async () => {
    const { clear } = await renderSettings()
    const read = deferred<void>()
    Object.assign(server, { logout: unreachable, me: heldUntil(read.promise, status(500, 'Internal Server Error')) })
    logOut()
    await waitFor(() => expect(meReads()).toBe(2))
    fireEvent.click(await screen.findByRole('button', { name: 'Log out of all devices' }))
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    read.resolve()
    await waitFor(() => expect(posts('/api/auth/logout-all')).toBe(1))
    await waitFor(() => expect(clear).toHaveBeenCalledTimes(1))
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGOUT_FAILED_MESSAGE)
    expect(nav.push).toHaveBeenCalledWith('/login')
  })

  it('posts nothing when the Log out it waited for took, and says why in a toast, since the page leaves with that Log out', async () => {
    const { client, clear } = await renderSettings()
    const answer = deferred<void>()
    server.logout = heldUntil(answer.promise, endsThisSession)
    logOut()
    await waitFor(() => expect(posts('/api/auth/logout')).toBe(1))
    const button = everywhere()
    fireEvent.click(button)
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    answer.resolve()
    const error = await logoutAllEnded(client, clear)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LoggedOutFirst)
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGGED_OUT_FIRST_MESSAGE)
    // The Log out took and leaves, and the page renders no section for a reader gone: a line in it could not show.
    expect(nav.push).toHaveBeenCalledWith('/')
    expect(screen.queryByRole('button', { name: 'Log out of all devices' })).toBeNull()
  })

  it("posts nothing when the Log out it waited for answered the API's 503, which cleared this browser's cookies, and says why", async () => {
    const { client, clear } = await renderSettings()
    const answer = deferred<void>()
    server.logout = heldUntil(answer.promise, incomplete)
    logOut()
    await waitFor(() => expect(posts('/api/auth/logout')).toBe(1))
    const button = everywhere()
    fireEvent.click(button)
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    answer.resolve()
    const error = await logoutAllEnded(client, clear)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LoggedOutFirst)
    // /me found no user: the Log out took, and warned in the 503's words that the server may still hold its session.
    expect(toasts.warning).toHaveBeenCalledExactlyOnceWith(LOGOUT_INCOMPLETE)
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGGED_OUT_FIRST_MESSAGE)
    expect(nav.push).toHaveBeenCalledWith('/')
  })

  it("posts nothing when the failed Log out it waited for read another reader: another tab signed in, whose account it would end", async () => {
    const { client, clear } = await renderSettings()
    const read = deferred<void>()
    // Another tab of this browser signs in as another account while this Log out's read is out: the cookies are that
    // account's, and /me names it.
    Object.assign(server, { logout: unreachable, me: heldUntil(read.promise, ok(other)) })
    logOut()
    await waitFor(() => expect(meReads()).toBe(2))
    fireEvent.click(await screen.findByRole('button', { name: 'Log out of all devices' }))
    await settle()
    read.resolve()
    const error = await logoutAllEnded(client, clear)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LogoutAllSuperseded)
    expect(nav.push).not.toHaveBeenCalledWith('/login')
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(other)
  })

  it('posts nothing and says nothing when a login overtook the Log out it waited for', async () => {
    const { client, clear } = await renderSettings()
    const answer = deferred<void>()
    server.logout = heldUntil(answer.promise, ok({ status: 'success' }))
    logOut()
    await waitFor(() => expect(posts('/api/auth/logout')).toBe(1))
    const button = everywhere()
    fireEvent.click(button)
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    // Another account's login lands meanwhile and its identity is accepted (app/login/page.tsx's order).
    act(() => {
      acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
      client.setQueryData(queryKeys.currentUser(), other)
    })
    answer.resolve()
    const error = await logoutAllEnded(client, clear)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LogoutAllSuperseded)
    expect(toasts.error).not.toHaveBeenCalled()
    expect(nav.push).not.toHaveBeenCalled()
  })

  it('posts nothing for a login accepted as the Log out it waited for settles, though that Log out did not take', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    markSessionActive()
    server.logout = unreachable
    // The Log out's request fails and /me names the reader: it did not take, and says so to its control, in whose turn
    // another account's login is accepted (app/login/page.tsx's order).
    const loggingOut = logoutAndResetAccount(client, logout, (succeeded) => {
      if (succeeded) return
      acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
      client.setQueryData(queryKeys.currentUser(), other)
    }).catch(() => undefined)
    const allSessions = logoutAllInTurn().catch((error: unknown) => error)
    await loggingOut
    expect(await allSessions).toBeInstanceOf(LogoutAllSuperseded)
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(other)
  })
})

describe('a Log out pressed while "Log out of all devices" runs waits for it', () => {
  it('and settles with it when it logs every session out: no request of its own, and the one leave is for /login', async () => {
    const { clear } = await renderSettings()
    const answer = deferred<void>()
    server.logoutAll = heldUntil(answer.promise, endsEverySession)
    fireEvent.click(everywhere())
    await waitFor(() => expect(posts('/api/auth/logout-all')).toBe(1))
    logOut()
    await settle()
    expect(posts('/api/auth/logout')).toBe(0)
    answer.resolve()
    await waitFor(() => expect(clear).toHaveBeenCalledTimes(1))
    await settle()
    expect(posts('/api/auth/logout')).toBe(0)
    expect(posts('/api/auth/logout-all')).toBe(1)
    expect(nav.push).toHaveBeenCalledWith('/login')
    expect(nav.push).not.toHaveBeenCalledWith('/')
    expect(toasts.error).not.toHaveBeenCalled()
  })

  it('and, when it fails, logs out on its own as a fresh press would: its own request, and its control leaves', async () => {
    const { clear } = await renderSettings()
    const answer = deferred<void>()
    server.logoutAll = heldUntil(answer.promise, unreachable)
    fireEvent.click(everywhere())
    await waitFor(() => expect(posts('/api/auth/logout-all')).toBe(1))
    logOut()
    await settle()
    // It waits: no request of its own while the logout of every session is out.
    expect(posts('/api/auth/logout')).toBe(0)
    answer.resolve()
    // That one failed and left the session, whose control's line may be gone with its page: this press logs out on its
    // own, and its control's continuation leaves.
    await waitFor(() => expect(posts('/api/auth/logout')).toBe(1))
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/'))
    expect(nav.refresh).toHaveBeenCalledTimes(1)
    expect(posts('/api/auth/logout-all')).toBe(1)
    expect(clear).not.toHaveBeenCalled()
  })
})

describe('"Log out of all devices" with no Log out under way', () => {
  it('logs every session out, then clears the cache and leaves for /login', async () => {
    const { clear } = await renderSettings()
    fireEvent.click(everywhere())
    await waitFor(() => expect(clear).toHaveBeenCalledTimes(1))
    expect(posts('/api/auth/logout-all')).toBe(1)
    expect(nav.push).toHaveBeenCalledWith('/login')
    expect(toasts.error).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(false)
  })

  it('that fails says why in the section, keeps the account, and puts the session flag back, so a lapsed access cookie still renews', async () => {
    const { client, clear } = await renderSettings()
    server.logoutAll = unreachable
    fireEvent.click(everywhere())
    expect(await screen.findByText('Could not reach the server. Try again in a moment.')).toBeInTheDocument()
    await settle()
    expect(hasActiveSession()).toBe(true)
    expect(clear).not.toHaveBeenCalled()
    expect(nav.push).not.toHaveBeenCalled()
    // The access cookie lapses: the next read of /me renews the session from the refresh cookie, and names the reader.
    Object.assign(server, { me: lapsed, refresh: renews })
    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(reader)
  })

  it('called again while it runs, joins it: one request', async () => {
    markSessionActive()
    const answer = deferred<void>()
    server.logoutAll = heldUntil(answer.promise, endsEverySession)
    const first = logoutAllInTurn()
    expect(logoutAllInTurn()).toBe(first)
    answer.resolve()
    await first
    expect(posts('/api/auth/logout-all')).toBe(1)
  })
})
