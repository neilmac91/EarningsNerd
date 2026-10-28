import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import api, { ensureRefreshed } from '@/lib/api/client'
import { LogoutAllSuperseded, type CurrentUser } from '@/features/auth/api/auth-api'
import {
  LOGGED_OUT_FIRST_MESSAGE, LOGOUT_FAILED_MESSAGE, LoggedOutFirst, acceptLoginAndResetAccount, logoutAllInTurn, subscribeAccountQueryReset,
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
 * the Log out did not take (its request failed and /me still names the reader), it posts. When the Log out took, this
 * device has no session left to end the others with: it posts nothing and says so, in a toast, since the page leaves
 * with that Log out. When a login overtook the Log out, it posts nothing and says nothing. A Log out pressed while it
 * runs joins it: one request, one outcome. Beside the flight, before E157, its `beginLogout` cleared the session flag
 * a failed Log out's read of /me needs, so a lapsed access cookie read as a guest and that Log out left as logged out
 * with the refresh cookie alive (#1496's review), and a Log out's reset lifted its refresh fence or ended it as
 * superseded.
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

const refused = async (): Promise<void> => { throw { response: { status: 401 } } }
/** A logout that took: its answer clears this browser's cookies, so /me then answers no user, and so does the logout
    of every session, whose route needs the access cookie (`get_current_user`). */
const endsThisSession: Answer = async (config) => {
  Object.assign(server, { me: status(401, 'Not authenticated'), logoutAll: status(401, 'Not authenticated'), refresh: refused, renewed: false })
  return ok({ status: 'success' })(config)
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

/** The settings page under the site header, once both have read the reader, with the client and a watch on its clear(),
    which only a logout of every session that took calls (ConnectedAccounts). */
async function renderSettings() {
  const client = new QueryClient({ defaultOptions: QUERY_CLIENT_DEFAULTS })
  clients.push(client)
  disposers.push(subscribeAccountQueryReset(client))
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
/** How the logout of every session ended, read from its mutation once it has: its error, or null for a success. */
const settledLogoutAll = async (client: QueryClient) => {
  await waitFor(() => expect(client.getMutationCache().getAll().map((mutation) => mutation.state.status)).toEqual([expect.stringMatching(/^(?:success|error)$/)]))
  return client.getMutationCache().getAll()[0].state.error
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
    const error = await settledLogoutAll(client)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LoggedOutFirst)
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGGED_OUT_FIRST_MESSAGE)
    expect(clear).not.toHaveBeenCalled()
    // The Log out took and leaves, and the page renders no section for a reader gone: a line in it could not show.
    expect(nav.push).toHaveBeenCalledWith('/')
    expect(screen.queryByRole('button', { name: 'Log out of all devices' })).toBeNull()
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
    const error = await settledLogoutAll(client)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LogoutAllSuperseded)
    expect(clear).not.toHaveBeenCalled()
    expect(toasts.error).not.toHaveBeenCalled()
    expect(nav.push).not.toHaveBeenCalled()
  })
})

describe('a Log out pressed while "Log out of all devices" runs joins it: one request, one outcome', () => {
  it('when every session is logged out: no request of its own, and the one leave is for /login', async () => {
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

  it('when it fails: no request and no report of its own, the section says what failed, and the account stays', async () => {
    const { clear } = await renderSettings()
    const answer = deferred<void>()
    server.logoutAll = heldUntil(answer.promise, unreachable)
    fireEvent.click(everywhere())
    await waitFor(() => expect(posts('/api/auth/logout-all')).toBe(1))
    logOut()
    await settle()
    expect(posts('/api/auth/logout')).toBe(0)
    answer.resolve()
    expect(await screen.findByText('Could not reach the server. Try again in a moment.')).toBeInTheDocument()
    await settle()
    expect(posts('/api/auth/logout')).toBe(0)
    expect(posts('/api/auth/logout-all')).toBe(1)
    expect(toasts.error).not.toHaveBeenCalled()
    expect(clear).not.toHaveBeenCalled()
    expect(nav.push).not.toHaveBeenCalled()
    // Still signed in, with the account menu's Log out to press again.
    fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    screen.getByRole('menuitem', { name: 'Log out' })
  })
})

describe('"Log out of all devices" with no Log out under way, as before', () => {
  it('logs every session out, then clears the cache and leaves for /login', async () => {
    const { clear } = await renderSettings()
    fireEvent.click(everywhere())
    await waitFor(() => expect(clear).toHaveBeenCalledTimes(1))
    expect(posts('/api/auth/logout-all')).toBe(1)
    expect(nav.push).toHaveBeenCalledWith('/login')
    expect(toasts.error).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(false)
  })

  it('refused for a login accepted while it waits for the refresh in flight, posts nothing, clears nothing, leaves for nothing and says nothing', async () => {
    const { client, clear } = await renderSettings()
    const answered = deferred<void>()
    vi.mocked(refreshAccessToken).mockImplementation(() => answered.promise)
    const refreshing = ensureRefreshed()
    fireEvent.click(everywhere())
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    act(() => {
      acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
      client.setQueryData(queryKeys.currentUser(), other)
    })
    answered.resolve()
    await refreshing
    const error = await settledLogoutAll(client)
    await settle()
    expect(posts('/api/auth/logout-all')).toBe(0)
    expect(error).toBeInstanceOf(LogoutAllSuperseded)
    expect(clear).not.toHaveBeenCalled()
    expect(nav.push).not.toHaveBeenCalled()
    expect(toasts.error).not.toHaveBeenCalled()
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
