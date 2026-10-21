import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import api from '@/lib/api/client'
import { logout, type CurrentUser } from '@/features/auth/api/auth-api'
import {
  LOGOUT_FAILED_MESSAGE, LOGOUT_UNCHECKED_MESSAGE, acceptLoginAndResetAccount, logoutAndResetAccount, subscribeAccountQueryReset,
} from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getExplicitSessionGeneration, getSessionGeneration, hasActiveSession, markSessionActive, notifySessionLost } from '@/lib/api/session'
import { refreshAccessToken } from '@/lib/api/refresh'
import { queryKeys } from '@/lib/queryKeys'
import { QUERY_CLIENT_DEFAULTS } from '@/app/providers'
import Header from '@/components/Header'
import DashboardPage from '@/app/dashboard/page'

/**
 * A logout whose request fails (a network error, a 5xx, the API's 504) asks /me before it acts, from every control
 * that logs out: the site header's account menu, its mobile menu and the dashboard's own button. The reader's account
 * stays on screen while /me is read. A user who comes back means the logout did not take: the reader is told, nothing
 * navigates, and focus goes back to the control that opened a menu. No user (the API's 503 clears the session cookies)
 * proceeds as a logout that succeeded. A read that fails too reports the logout as not taken and keeps the account,
 * and its Log out, for another try. The read can renew a lapsed access cookie from the refresh cookie, as any request
 * of a signed-in tab does, so a lapsed access cookie is not mistaken for a logout. The dashboard leaves for /login only
 * for a confirmed guest. A login accepted meanwhile owns the tab.
 *
 * The requests run through the real API client and auth API, with the adapter answering, so the interceptor's
 * statuses, the session flag and the generation fences are the ones the app runs; the refresh is the one stub, and the
 * client is built as Providers builds the app's: its defaults (a read stays fresh for a minute) and its reset of a
 * lost session.
 */

const nav = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }))
const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
const tracked = vi.hoisted(() => ({ identify: vi.fn(), logout: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => nav, usePathname: () => '/dashboard' }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
vi.mock('sonner', () => ({ toast: toasts }))
vi.mock('@/lib/analytics', () => ({ default: tracked }))
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))
// The header's chrome and the dashboard's other sections and reads are not under test.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/features/notifications/components/NotificationBell', () => ({ default: () => null }))
vi.mock('@/features/subscriptions/components/TrialBanner', () => ({ default: () => null }))
vi.mock('@/features/companies/components/CompanySearch', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/FilingFeed', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/EarningsCalendar', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/YourCompanies', () => ({ default: () => null }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getUsage: vi.fn(async () => ({ summaries_used: 1, summaries_limit: 3, is_pro: false })),
  getSubscriptionStatus: vi.fn(async () => ({ is_pro: false, plan: 'free', status: null, trial_end: null })),
  createPortalSession: vi.fn(),
}))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getSavedSummaries: vi.fn(async () => []), deleteSavedSummary: vi.fn() }))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({ getWatchlistInsights: vi.fn(async () => []) }))

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
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}
/** Let pending fetches, renders and effects run. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

const LOGOUT_INCOMPLETE = 'This browser is logged out, but we could not end the session on the server.'
/** What the API answers: /me, the logout POST and the refresh, each replaceable mid-test; every request is recorded. */
const server = {
  me: ok(reader),
  logout: ok({ status: 'success' }),
  /** The refresh cookie: refused (gone, as the 503 leaves it) unless a case renews the session. */
  refresh: async (): Promise<void> => { throw { response: { status: 401 } } },
  renewed: false,
  requests: [] as string[],
}
const refused = server.refresh
const renews = async () => { server.renewed = true }
/** The access cookie has lapsed: /me answers 401 until the refresh renews the session. */
const lapsed: Answer = (config) => (server.renewed ? ok(reader) : status(401, 'Could not validate credentials'))(config)
const meReads = () => server.requests.filter((request) => request === 'get /api/auth/me').length
const originalAdapter = api.defaults.adapter
const clients: QueryClient[] = []
const disposers: (() => void)[] = []
/** A client as Providers builds the app's: its defaults, and the account reset when a request confirms the session lost. */
const newClient = () => {
  const client = new QueryClient({ defaultOptions: QUERY_CLIENT_DEFAULTS })
  clients.push(client)
  disposers.push(subscribeAccountQueryReset(client))
  return client
}

beforeEach(() => {
  advanceSessionGeneration()
  clearSessionActive()
  Object.assign(server, { me: ok(reader), logout: ok({ status: 'success' }), refresh: refused, renewed: false, requests: [] })
  vi.mocked(refreshAccessToken).mockImplementation(() => server.refresh())
  api.defaults.adapter = async (config) => {
    server.requests.push(`${config.method} ${config.url}`)
    if (config.url === '/api/auth/me') return server.me(config)
    if (config.url === '/api/auth/logout') return server.logout(config)
    throw new Error(`unexpected request ${config.method} ${config.url}`)
  }
})
afterEach(() => {
  cleanup()
  disposers.splice(0).forEach((dispose) => dispose())
  clients.splice(0).forEach((client) => client.clear())
  api.defaults.adapter = originalAdapter
  onlineManager.setOnline(true)
  vi.clearAllMocks()
})

/** Each control that logs out: what shows its page loaded and signed in, its Log out, where a successful logout goes,
 *  what shows the reader still signed in with a Log out to press again, and the control that opened its menu. */
const CONTROLS = {
  'account menu': {
    render: () => render(<QueryClientProvider client={newClient()}><Header /></QueryClientProvider>),
    loaded: () => screen.findByRole('button', { name: 'Account menu' }),
    logOut: () => {
      fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
      return screen.getByRole('menuitem', { name: 'Log out' })
    },
    destination: '/',
    signedIn: async () => {
      fireEvent.click(await screen.findByRole('button', { name: 'Account menu' }))
      await screen.findByRole('menuitem', { name: 'Log out' })
    },
    opener: () => screen.getByRole('button', { name: 'Account menu' }),
  },
  'mobile menu': {
    render: () => render(<QueryClientProvider client={newClient()}><Header /></QueryClientProvider>),
    loaded: () => screen.findByRole('button', { name: 'Account menu' }),
    logOut: () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
      return screen.getByRole('button', { name: 'Log out' })
    },
    destination: '/',
    signedIn: async () => {
      fireEvent.click(await screen.findByRole('button', { name: 'Open menu' }))
      await screen.findByRole('button', { name: 'Log out' })
    },
    opener: () => screen.getByRole('button', { name: 'Open menu' }),
  },
  dashboard: {
    render: () => render(<QueryClientProvider client={newClient()}><DashboardPage /></QueryClientProvider>),
    loaded: () => screen.findByText('Welcome back, Reader'),
    logOut: () => screen.getByRole('button', { name: 'Log out' }),
    destination: '/login',
    signedIn: async () => {
      await screen.findByText('Welcome back, Reader')
      screen.getByRole('button', { name: 'Log out' })
    },
    opener: undefined,
  },
} as const
const controls = Object.keys(CONTROLS) as (keyof typeof CONTROLS)[]

describe.each(controls)('a logout from the %s', (name) => {
  const control = CONTROLS[name]
  /** Render the signed-in page; once its first /me has answered, the API gives these answers, then the press. */
  const pressAfter = async (answers: Partial<typeof server>) => {
    control.render()
    await control.loaded()
    Object.assign(server, answers)
    fireEvent.click(control.logOut())
  }

  it('that fails while the session lives on tells the reader, navigates nowhere and still shows the user', async () => {
    await pressAfter({ logout: unreachable })
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    expect(meReads()).toBe(2)
    await control.signedIn()
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
    expect(nav.refresh).not.toHaveBeenCalled()
    expect(tracked.logout).not.toHaveBeenCalled()
    expect(refreshAccessToken).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(true)
  })

  it('that fails once the access cookie has lapsed renews the session, tells the reader and stays', async () => {
    await pressAfter({ logout: unreachable, me: lapsed, refresh: renews })
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    // /me's 401 was the lapsed access cookie: the refresh cookie renewed the session, and /me answered with the reader.
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(meReads()).toBe(3)
    await control.signedIn()
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
    expect(tracked.logout).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(true)
  })

  it('answered 503 with the session cookies cleared proceeds as a logout that succeeded', async () => {
    await pressAfter({ logout: status(503, LOGOUT_INCOMPLETE), me: status(401, 'Could not validate credentials') })
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith(control.destination))
    // /me's 401 tried the refresh cookie, which the 503 cleared too.
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(meReads()).toBe(2)
    expect(nav.refresh).toHaveBeenCalledTimes(1)
    expect(toasts.error).not.toHaveBeenCalled()
    expect(tracked.logout).toHaveBeenCalledTimes(name === 'dashboard' ? 1 : 0)
    expect(hasActiveSession()).toBe(false)
  })

  it('that succeeds navigates as before and reads /me no more', async () => {
    await pressAfter({})
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith(control.destination))
    await settle()
    expect(nav.refresh).toHaveBeenCalledTimes(1)
    expect(toasts.error).not.toHaveBeenCalled()
    expect(tracked.logout).toHaveBeenCalledTimes(name === 'dashboard' ? 1 : 0)
    expect(meReads()).toBe(1)
  })

  it.each(['offline', 'answering 500'])('whose /me read fails too (%s) tells the reader and keeps the account and its Log out', async (how) => {
    control.render()
    await control.loaded()
    if (how === 'offline') onlineManager.setOnline(false)
    Object.assign(server, { logout: unreachable, me: how === 'offline' ? unreachable : status(500, 'Internal Server Error') })
    fireEvent.click(control.logOut())
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_UNCHECKED_MESSAGE))
    expect(meReads()).toBe(2)
    await control.signedIn()
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
    expect(nav.refresh).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(true)
  })
})

describe.each(['account menu', 'mobile menu'] as const)('a logout from the %s that does not take', (name) => {
  it('hands focus back to the control that opened the menu', async () => {
    const control = CONTROLS[name]
    control.render()
    await control.loaded()
    server.logout = unreachable
    // Pressed from the keyboard: Log out holds focus, and leaves with the menu.
    const logOut = control.logOut()
    logOut.focus()
    fireEvent.click(logOut)
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await waitFor(() => expect(document.activeElement).toBe(control.opener()))
  })
})

describe('the dashboard while a failed logout reads /me', () => {
  it.each(['dashboard', 'site header'])('keeps the reader on screen, from the %s control, and leaves for nothing', async (from) => {
    const client = newClient()
    render(<QueryClientProvider client={client}><Header /><DashboardPage /></QueryClientProvider>)
    await screen.findByText('Welcome back, Reader')
    const check = deferred<CurrentUser>()
    server.logout = unreachable
    server.me = async (config) => ok(await check.promise)(config)
    if (from === 'dashboard') {
      fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
    } else {
      fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
      fireEvent.click(screen.getByRole('menuitem', { name: 'Log out' }))
    }
    // /me is being read again, and the reader's account stays on screen meanwhile: no guard sees a guest.
    await waitFor(() => expect(meReads()).toBe(2))
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(reader)
    expect(client.getQueryState(queryKeys.currentUser())?.fetchStatus).toBe('fetching')
    await settle()
    screen.getByText('Welcome back, Reader')
    screen.getByRole('button', { name: 'Account menu' })
    expect(nav.push).not.toHaveBeenCalled()
    check.resolve(reader)
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
  })
})

describe('the dashboard sends a confirmed guest to /login', () => {
  it('when /me answers no user', async () => {
    server.me = status(401, 'Not authenticated')
    render(<QueryClientProvider client={newClient()}><DashboardPage /></QueryClientProvider>)
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/login'))
    expect(meReads()).toBe(1)
  })

  it('once a lost session resets the read', async () => {
    const client = newClient()
    render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>)
    await screen.findByText('Welcome back, Reader')
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
    // Another request's 401 confirms the session gone (lib/api/client.ts), and the account resets (Providers).
    act(() => notifySessionLost(getSessionGeneration()))
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/login'))
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
  })
})

describe('logoutAndResetAccount after a failed request', () => {
  const requestError = new Error('the logout request failed')
  const failing = async () => { throw requestError }

  it.each([
    ['no user', status(401, 'Could not validate credentials'), true],
    ['the reader', ok(reader), false],
    ['nothing', unreachable, false],
  ] as const)("when /me answers %s, resolves for a logout that took anyway, and rejects with the request's error for one that did not", async (_, me, tookAnyway) => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    server.me = me
    const continued = vi.fn()
    const settled = logoutAndResetAccount(client, failing, continued)
    if (tookAnyway) await expect(settled).resolves.toBeUndefined()
    else await expect(settled).rejects.toBe(requestError)
    expect(continued).toHaveBeenCalledExactlyOnceWith(tookAnyway)
  })

  it('lets a login accepted while /me was read own the tab: no continuation and no report', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    markSessionActive()
    const check = deferred<null>()
    server.logout = unreachable
    server.me = async (config) => ok(await check.promise)(config)
    const continued = vi.fn()
    const settled = logoutAndResetAccount(client, logout, continued).catch((error: unknown) => error)
    await waitFor(() => expect(meReads()).toBe(1))
    // Another account's login lands meanwhile and its identity is accepted (app/login/page.tsx's order).
    acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
    client.setQueryData(queryKeys.currentUser(), other)
    check.resolve(null)
    expect(await settled).toMatchObject({ status: 0 })
    expect(continued).not.toHaveBeenCalled()
    expect(toasts.error).not.toHaveBeenCalled()
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(other)
  })

  it('offline, reports at once rather than holding the logout until the connection returns', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    Object.assign(server, { logout: unreachable, me: unreachable })
    const continued = vi.fn()
    onlineManager.setOnline(false)
    await expect(logoutAndResetAccount(client, logout, continued)).rejects.toMatchObject({ status: 0 })
    expect(meReads()).toBe(1)
    expect(toasts.error).toHaveBeenCalledWith(LOGOUT_UNCHECKED_MESSAGE)
    expect(continued).toHaveBeenCalledWith(false)
  })
})
