import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { CanceledError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import api from '@/lib/api/client'
import { getCurrentUserSafe, logout, type CurrentUser } from '@/features/auth/api/auth-api'
import {
  LOGOUT_FAILED_MESSAGE, SESSION_READ_LIMIT_MS, acceptLoginAndResetAccount, logoutAndResetAccount, subscribeAccountQueryReset,
} from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getExplicitSessionGeneration, getSessionGeneration, hasActiveSession, markSessionActive, notifySessionLost } from '@/lib/api/session'
import { refreshAccessToken } from '@/lib/api/refresh'
import { queryKeys } from '@/lib/queryKeys'
import { QUERY_CLIENT_DEFAULTS } from '@/app/providers'
import Header from '@/components/Header'
import DashboardPage from '@/app/dashboard/page'
import WatchlistDashboardPage from '@/app/dashboard/watchlist/page'
import AdminLayout from '@/app/admin/layout'
import { LOGOUT_CALL_SITES } from './logoutCallSites'

/**
 * A logout whose request fails (a network error, a 5xx, the API's 504) asks /me before it acts, from every control
 * that logs out: the site header's account menu, its mobile menu and the dashboard's own button. The reader's account
 * stays on screen while /me is read. A user who comes back means the logout did not take: the reader is told, nothing
 * navigates, and focus goes back to the control that opened a menu. No user (the API's 503 clears the session cookies)
 * proceeds as a logout that succeeded, and the reader is warned in the 503's own words that the server may still hold
 * the session. A read that fails too reports the logout as not taken and keeps the account, and its Log out, for
 * another try. The read can renew a lapsed access cookie from the refresh cookie, as any request of a signed-in tab
 * does, so a lapsed access cookie is not mistaken for a logout; a second press while the logout runs joins it (one
 * request, one report), so it cannot take that renewal away. The dashboard leaves for /login only for a confirmed
 * guest, and the watchlist and the admin section, whose guards wait for one too, show the shared account card, named
 * for each route, when the first /me read fails. A login accepted meanwhile owns the tab.
 *
 * The requests run through the real API client and auth API, with the adapter answering, so the interceptor's
 * statuses, the session flag and the generation fences are the ones the app runs; the refresh is the one stub, and the
 * client is built as Providers builds the app's: its defaults (a read stays fresh for a minute) and its reset of a
 * lost session.
 */

const nav = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn(), back: vi.fn(), forward: vi.fn(), prefetch: vi.fn() }))
const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn(), warning: vi.fn() }))
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
vi.mock('@/features/watchlist/components/WatchlistAddSearch', () => ({ default: () => null }))

const reader: CurrentUser = {
  id: 7, email: 'reader@example.com', full_name: 'Reader', is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}
const other: CurrentUser = { ...reader, id: 8, email: 'other@example.com', full_name: 'Other' }
const admin: CurrentUser = { ...reader, id: 9, email: 'admin@example.com', full_name: 'Admin', is_admin: true }

type Answer = (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>
const ok = (data: unknown): Answer => async (config) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const status = (code: number, detail: string): Answer => async (config) => {
  throw Object.assign(new Error(`Request failed with status code ${code}`), { config, response: { status: code, data: { detail } } })
}
const unreachable: Answer = async (config) => { throw Object.assign(new Error('Network Error'), { config }) }
/** A status whose body is a page, not the API's JSON: what a proxy or load balancer in front of it answers. */
const page = (code: number): Answer => async (config) => {
  throw Object.assign(new Error(`Request failed with status code ${code}`), { config, response: { status: code, data: '<html>Service Unavailable</html>' } })
}
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
const logoutPosts = () => server.requests.filter((request) => request === 'post /api/auth/logout').length
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

/** Every write to window.location (itself or a part of it) and every load it is asked for, recorded and not run. The
    page reads the real location through it; `location` and `window.location` are the same global here. It stands on an
    empty object: jsdom's location holds assign, replace and reload as fixed properties, which a proxy of it cannot
    report as anything else. */
const locationChanges: string[] = []
const realLocation = window.location
const realLocationProperty = Object.getOwnPropertyDescriptor(window, 'location') as PropertyDescriptor
const recordingLocation = new Proxy({} as Location, {
  get(_stand, key) {
    if (key === 'assign' || key === 'replace' || key === 'reload') {
      return (...args: unknown[]) => { locationChanges.push(`location.${key}(${args.map(String).join(', ')})`) }
    }
    const value: unknown = Reflect.get(realLocation, key, realLocation)
    return typeof value === 'function' ? value.bind(realLocation) : value
  },
  set(_target, key, value) {
    locationChanges.push(`location.${String(key)} = ${String(value)}`)
    return true
  },
})
/** jsdom's virtual console, which vitest's jsdom environment exposes on `globalThis.jsdom`. */
interface JsdomConsole {
  on(event: 'jsdomError', listener: (error: Error) => void): unknown
  off(event: 'jsdomError', listener: (error: Error) => void): unknown
}
/** Each load jsdom reports as not implemented: one of another URL, or a reload(), asked of the real location
    ("navigation to another Document"), which `document.location` reaches without passing through window.location, so
    the stand-in above never sees it; and a form's submit() or requestSubmit(). jsdom passes over a load of the URL the
    document is at without a word, so each case parks the document at a path the app has no page for. A load of that
    parked URL itself (`document.location.href = document.location.href`) still goes unheard. */
const jsdomLoads: string[] = []
const jsdomConsole = (globalThis as unknown as { jsdom: { virtualConsole: JsdomConsole } }).jsdom.virtualConsole
const LOAD_REPORT = /^Not implemented: (navigation|HTMLFormElement's (submit|requestSubmit)\(\) method)/
const hearLoad = (error: Error) => { if (LOAD_REPORT.test(error.message)) jsdomLoads.push(error.message) }
const realUrl = window.location.href
const PARKED_PATH = '/failed-logout-spec'
/** The history moves and window.open, held for each case so none runs. */
const historyMoves: MockInstance[] = []
/** No navigation: none of the router's moves, no history move or window.open, nothing set on or loaded by
    window.location, and no load jsdom reports (another URL or a reload through document.location, a form's submit).
    logoutCallSitesGate.spec.ts reads only the calls of logoutAndResetAccount and the code around them; the helper
    itself, the API client and the session reset are imported code it cannot read, so this watch is the one check
    that a failed logout navigates nowhere through them. */
const expectNoNavigation = () => {
  for (const move of ['push', 'replace', 'back', 'forward', 'refresh'] as const) expect(nav[move], `router.${move}`).not.toHaveBeenCalled()
  for (const move of ['back', 'forward', 'go'] as const) expect(window.history[move], `history.${move}`).not.toHaveBeenCalled()
  expect(window.open, 'window.open').not.toHaveBeenCalled()
  expect(locationChanges, 'window.location').toEqual([])
  expect(jsdomLoads, 'a load jsdom reports (document.location, a form submit)').toEqual([])
}

beforeEach(() => {
  locationChanges.length = 0
  jsdomLoads.length = 0
  jsdomConsole.on('jsdomError', hearLoad)
  window.history.replaceState(null, '', PARKED_PATH)
  Object.defineProperty(window, 'location', {
    configurable: true,
    get: () => recordingLocation,
    set: (value: unknown) => { locationChanges.push(`location = ${String(value)}`) },
  })
  for (const move of ['back', 'forward', 'go'] as const) historyMoves.push(vi.spyOn(window.history, move).mockImplementation(() => {}))
  historyMoves.push(vi.spyOn(window, 'open').mockImplementation(() => null))
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
  Object.defineProperty(window, 'location', realLocationProperty)
  historyMoves.splice(0).forEach((spy) => spy.mockRestore())
  window.history.replaceState(null, '', realUrl)
  jsdomConsole.off('jsdomError', hearLoad)
  vi.clearAllMocks()
})

/** Each control that logs out: the file its call of logoutAndResetAccount sits in (LOGOUT_CALL_SITES), what shows its
 *  page loaded and signed in, its Log out, where a successful logout goes, what shows the reader still signed in with a
 *  Log out to press again, and the control that opened its menu. */
const CONTROLS = {
  'account menu': {
    site: 'features/auth/components/UserMenu.tsx',
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
    site: 'components/Header.tsx',
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
    site: 'app/dashboard/page.tsx',
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

describe('the controls whose failure cases run below', () => {
  it('include one for each call of logoutAndResetAccount the gate inventories, so a new one gets its cases', () => {
    expect(controls.map((name) => CONTROLS[name].site).sort()).toEqual(Object.keys(LOGOUT_CALL_SITES).sort())
  })
})

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
    expectNoNavigation()
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
    expectNoNavigation()
    expect(tracked.logout).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(true)
  })

  it("answered 503 with the session cookies cleared proceeds as a logout that succeeded, and warns in the 503's words", async () => {
    await pressAfter({ logout: status(503, LOGOUT_INCOMPLETE), me: status(401, 'Could not validate credentials') })
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith(control.destination))
    // /me's 401 tried the refresh cookie, which the 503 cleared too.
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(meReads()).toBe(2)
    expect(nav.refresh).toHaveBeenCalledTimes(1)
    expect(toasts.error).not.toHaveBeenCalled()
    // The server may still hold the session it could not end, so the reader hears it as they leave.
    expect(toasts.warning).toHaveBeenCalledExactlyOnceWith(LOGOUT_INCOMPLETE)
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

  it('pressed again while its request is out sends that one request and reports once', async () => {
    const answer = deferred<void>()
    await pressAfter({ logout: heldUntil(answer.promise, unreachable) })
    await waitFor(() => expect(logoutPosts()).toBe(1))
    fireEvent.click(control.logOut())
    answer.resolve()
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await control.signedIn()
    await settle()
    expect(logoutPosts()).toBe(1)
    expect(toasts.error).toHaveBeenCalledTimes(1)
    expectNoNavigation()
    expect(hasActiveSession()).toBe(true)
  })

  it('pressed again while /me is read leaves the read to renew a lapsed access cookie, reports once and stays', async () => {
    const answer = deferred<void>()
    await pressAfter({ logout: unreachable, me: heldUntil(answer.promise, lapsed), refresh: renews })
    // The request failed and /me is being read, with the account on screen: the reader presses Log out again. Its own
    // logout would clear the session flag before /me's 401 lands, and that 401 would read as a guest (E133's flag).
    await waitFor(() => expect(meReads()).toBe(2))
    fireEvent.click(control.logOut())
    answer.resolve()
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    expect(refreshAccessToken).toHaveBeenCalledTimes(1)
    expect(logoutPosts()).toBe(1)
    await control.signedIn()
    await settle()
    expect(toasts.error).toHaveBeenCalledTimes(1)
    expectNoNavigation()
    expect(tracked.logout).not.toHaveBeenCalled()
    expect(hasActiveSession()).toBe(true)
  })

  it.each(['offline', 'answering 500'])('whose /me read fails too (%s) tells the reader and keeps the account and its Log out', async (how) => {
    control.render()
    await control.loaded()
    if (how === 'offline') onlineManager.setOnline(false)
    Object.assign(server, { logout: unreachable, me: how === 'offline' ? unreachable : status(500, 'Internal Server Error') })
    fireEvent.click(control.logOut())
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    expect(meReads()).toBe(2)
    await control.signedIn()
    await settle()
    expectNoNavigation()
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
    await settle()
    expectNoNavigation()
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
    expectNoNavigation()
    check.resolve(reader)
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await settle()
    expectNoNavigation()
  })
})

describe("the dashboard's Log out while its logout runs", () => {
  it('reads unavailable and busy, and a press then sends nothing more', async () => {
    render(<QueryClientProvider client={newClient()}><DashboardPage /></QueryClientProvider>)
    await screen.findByText('Welcome back, Reader')
    const answer = deferred<void>()
    server.logout = heldUntil(answer.promise, ok({ status: 'success' }))
    const logOut = screen.getByRole('button', { name: 'Log out' })
    expect(logOut).not.toHaveAttribute('aria-disabled')
    fireEvent.click(logOut)
    await waitFor(() => expect(logOut).toHaveAttribute('aria-disabled', 'true'))
    expect(logOut).toHaveAttribute('aria-busy', 'true')
    fireEvent.click(logOut)
    answer.resolve()
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/login'))
    expect(logoutPosts()).toBe(1)
    expect(tracked.logout).toHaveBeenCalledTimes(1)
  })
})

describe("the dashboard's Log out after a logout that did not take", () => {
  it('reads available again, and a press then sends a request of its own', async () => {
    render(<QueryClientProvider client={newClient()}><DashboardPage /></QueryClientProvider>)
    await screen.findByText('Welcome back, Reader')
    server.logout = unreachable
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
    await waitFor(() => expect(toasts.error).toHaveBeenCalledTimes(1))
    const logOut = screen.getByRole('button', { name: 'Log out' })
    await waitFor(() => expect(logOut).not.toHaveAttribute('aria-disabled'))
    expect(logOut).not.toHaveAttribute('aria-busy')
    fireEvent.click(logOut)
    await waitFor(() => expect(toasts.error).toHaveBeenCalledTimes(2))
    await settle()
    expect(logoutPosts()).toBe(2)
    expectNoNavigation()
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

/** The routes whose guards wait for a confirmed guest beside the dashboard's: what renders each, the user it serves, and
 *  where focus lands when Try again loads it. */
const GUARDED = {
  '/dashboard/watchlist': {
    render: () => <WatchlistDashboardPage />,
    title: 'Unable to load your watchlist',
    user: reader,
    loaded: () => screen.findByRole('heading', { level: 1, name: 'Watchlist insights' }),
  },
  '/admin': {
    render: () => <AdminLayout><p>Admin page</p></AdminLayout>,
    title: 'Unable to load the admin section',
    user: admin,
    loaded: () => screen.findByRole('navigation', { name: 'Admin sections' }),
  },
} as const

describe.each(Object.keys(GUARDED) as (keyof typeof GUARDED)[])('%s, when the first /me read answers 500', (path) => {
  it('shows the account card, named for the route, with Try again and Go to login, leaves for nothing, and Try again loads it', async () => {
    const route = GUARDED[path]
    server.me = status(500, 'Internal Server Error')
    render(<QueryClientProvider client={newClient()}>{route.render()}</QueryClientProvider>)
    const card = await screen.findByRole('alert')
    within(card).getByText(route.title)
    const retry = within(card).getByRole('button', { name: 'Try again' })
    expect(within(card).getByRole('link', { name: 'Go to login' })).toHaveAttribute('href', '/login')
    await settle()
    expect(meReads()).toBe(1)
    expectNoNavigation()
    // Pressed from the keyboard: /me is read again, the route replaces the card, and focus goes to it.
    server.me = ok(route.user)
    retry.focus()
    fireEvent.click(retry)
    const target = await route.loaded()
    await waitFor(() => expect(document.activeElement).toBe(target))
    expect(meReads()).toBe(2)
    expectNoNavigation()
  })
})

/** Every route that renders the account card, the two guarded above and the dashboard, with what shows it fully loaded:
    the dashboard's header and greeting and the watchlist's header render on their skeletons too, so a section only the
    loaded page renders marks it (the dashboard's Plan and usage, the watchlist's empty list). */
const CARD_ROUTES = {
  '/dashboard': {
    render: () => <DashboardPage />,
    title: 'Unable to load your dashboard',
    user: reader,
    loaded: () => screen.findByRole('heading', { level: 2, name: 'Plan and usage' }),
  },
  '/dashboard/watchlist': { ...GUARDED['/dashboard/watchlist'], loaded: () => screen.findByText('No watchlist companies yet') },
  '/admin': GUARDED['/admin'],
} as const

describe.each(Object.keys(CARD_ROUTES) as (keyof typeof CARD_ROUTES)[])('%s, when a refetch of /me fails with the user in hand', (path) => {
  it('keeps the page: the account card stands in only for a read that has no user', async () => {
    const route = CARD_ROUTES[path]
    server.me = ok(route.user)
    const client = newClient()
    render(<QueryClientProvider client={client}>{route.render()}</QueryClientProvider>)
    await route.loaded()
    await settle()
    // The whole page as it reads loaded, to hold against the page after the failed refetch.
    const page = document.body.textContent
    server.me = status(500, 'Internal Server Error')
    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await settle()
    expect(meReads()).toBe(2)
    expect(client.getQueryState(queryKeys.currentUser())).toMatchObject({ status: 'error', data: route.user })
    expect(screen.queryByText(route.title)).toBeNull()
    expect(document.body.textContent).toBe(page)
    expectNoNavigation()
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

  it.each([
    ["the API's own 503, in its words", status(503, LOGOUT_INCOMPLETE), LOGOUT_INCOMPLETE],
    ['a 503 page from in front of the API', page(503), undefined],
    ["a 500 in the API's words", status(500, 'Internal Server Error'), undefined],
    ['no answer', unreachable, undefined],
  ] as const)("after %s, a logout that took anyway warns only in the words of the API's 503", async (_, answer, warning) => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    markSessionActive()
    Object.assign(server, { logout: answer, me: status(401, 'Could not validate credentials') })
    const continued = vi.fn()
    await logoutAndResetAccount(client, logout, continued)
    expect(continued).toHaveBeenCalledExactlyOnceWith(true)
    if (warning) expect(toasts.warning).toHaveBeenCalledExactlyOnceWith(warning)
    else expect(toasts.warning).not.toHaveBeenCalled()
    expect(toasts.error).not.toHaveBeenCalled()
  })

  it.each([
    ['still answers the reader', ok(reader)],
    ['answers 500', status(500, 'Internal Server Error')],
    ['gets no answer', unreachable],
  ] as const)("after the API's own 503, a /me that %s reports the logout as not taken, and warns nothing", async (_, me) => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    markSessionActive()
    Object.assign(server, { logout: status(503, LOGOUT_INCOMPLETE), me })
    const continued = vi.fn()
    await expect(logoutAndResetAccount(client, logout, continued)).rejects.toMatchObject({ status: 503 })
    expect(continued).toHaveBeenCalledExactlyOnceWith(false)
    expect(toasts.error).toHaveBeenCalledExactlyOnceWith(LOGOUT_FAILED_MESSAGE)
    expect(toasts.warning).not.toHaveBeenCalled()
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

  it("after the API's own 503, a login accepted while /me was read owns the tab: the account that logged in hears no warning", async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    markSessionActive()
    const answer = deferred<CurrentUser>()
    server.logout = status(503, LOGOUT_INCOMPLETE)
    server.me = async (config) => ok(await answer.promise)(config)
    const continued = vi.fn()
    const settled = logoutAndResetAccount(client, logout, continued).catch((error: unknown) => error)
    await waitFor(() => expect(meReads()).toBe(1))
    // Another account's login lands meanwhile, in app/login/page.tsx's order: its identity is accepted, then its own read
    // of /me starts. The reset cancels the logout's read, which comes back with the reset's null, a guest, while the
    // login's read is unanswered: only the ownership check keeps the 503's warning from the new account.
    acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
    const login = client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })
    expect(await settled).toMatchObject({ status: 503 })
    expect(continued).not.toHaveBeenCalled()
    expect(toasts.warning).not.toHaveBeenCalled()
    expect(toasts.error).not.toHaveBeenCalled()
    answer.resolve(other)
    await expect(login).resolves.toEqual(other)
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(other)
  })

  it("reports a logout that did not take when /me's refresh never answers, and cancels the refresh, so its cookies cannot land over a login accepted after", async () => {
    // The access cookie has lapsed, so /me 401s and starts a refresh, which answers only when the case lets it. As in the
    // browser, a cancelled refresh fails at once, and an answer after that is dropped with the cookies it carries, which
    // `server.renewed` records when they land. The refresh is let go in `finally` too, so a failure here leaves none in
    // flight for the next case's logout to wait on.
    const stalled = deferred<void>()
    vi.mocked(refreshAccessToken).mockImplementation((_url, signal) => new Promise<void>((answer, fail) => {
      signal?.addEventListener('abort', () => fail(new CanceledError()))
      void stalled.promise.then(() => {
        if (signal?.aborted) return
        server.renewed = true
        answer()
      })
    }))
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const client = newClient()
      client.setQueryData(queryKeys.currentUser(), reader)
      markSessionActive()
      server.me = lapsed
      const continued = vi.fn()
      const settled = logoutAndResetAccount(client, failing, continued).catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(SESSION_READ_LIMIT_MS - 1)
      const refreshSignal = vi.mocked(refreshAccessToken).mock.calls[0][1] as AbortSignal
      expect(meReads()).toBe(1)
      expect(refreshSignal.aborted).toBe(false)
      expect(continued).not.toHaveBeenCalled()
      await vi.advanceTimersByTimeAsync(1)
      // Past the limit the read cannot tell, as a read that fails cannot: never a logout that took. The read and the
      // refresh are cancelled, and the identity stays as the logout found it.
      expect(refreshSignal.aborted).toBe(true)
      expect(continued).toHaveBeenCalledExactlyOnceWith(false)
      expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE)
      expect(await settled).toBe(requestError)
      expect(client.getQueryState(queryKeys.currentUser())).toMatchObject({ data: reader, status: 'success', fetchStatus: 'idle' })
      expect(hasActiveSession()).toBe(true)
      // Another account's login lands, and only then could the refresh have answered: its answer is dropped, so the
      // previous session's cookies do not replace the new login's, /me is not read again, and the new account stays.
      acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
      client.setQueryData(queryKeys.currentUser(), other)
      stalled.resolve()
      await vi.advanceTimersByTimeAsync(0)
      expect(server.renewed).toBe(false)
      expect(meReads()).toBe(1)
      expect(client.getQueryData(queryKeys.currentUser())).toEqual(other)
      expectNoNavigation()
    } finally {
      stalled.resolve()
      await vi.advanceTimersByTimeAsync(0)
      vi.useRealTimers()
    }
  })

  it('reports a logout that did not take when /me itself never answers, and cancels the read, so no late answer lands', async () => {
    // A /me request that never answers. Cancelled, it fails at once, as the browser's does.
    let meSignal: AbortSignal | undefined
    server.me = (config) => new Promise<AxiosResponse>((_answer, fail) => {
      meSignal = config.signal as AbortSignal
      meSignal.addEventListener('abort', () => fail(Object.assign(new CanceledError(), { config })))
    })
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const client = newClient()
      client.setQueryData(queryKeys.currentUser(), reader)
      markSessionActive()
      const continued = vi.fn()
      const settled = logoutAndResetAccount(client, failing, continued).catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(SESSION_READ_LIMIT_MS - 1)
      expect(meSignal?.aborted).toBe(false)
      expect(continued).not.toHaveBeenCalled()
      await vi.advanceTimersByTimeAsync(1)
      expect(meSignal?.aborted).toBe(true)
      expect(continued).toHaveBeenCalledExactlyOnceWith(false)
      expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE)
      expect(await settled).toBe(requestError)
      expect(client.getQueryState(queryKeys.currentUser())).toMatchObject({ data: reader, status: 'success', fetchStatus: 'idle' })
      expect(hasActiveSession()).toBe(true)
      expectNoNavigation()
    } finally {
      vi.useRealTimers()
    }
  })

  it("lets the reader's retry post at once after a logout whose refresh never answered", async () => {
    // The first logout cannot reach the API, and its /me read waits on a refresh that never answers. Had the limit left
    // that refresh in flight, the retry the toast invites would wait for it before posting (LOGOUT_REFRESH_WAIT_MS),
    // with the menus closed and nothing on screen. The refresh is let go in `finally`, as in the case above.
    const stalled = deferred<void>()
    vi.mocked(refreshAccessToken).mockImplementation((_url, signal) => new Promise<void>((answer, fail) => {
      signal?.addEventListener('abort', () => fail(new CanceledError()))
      void stalled.promise.then(() => { if (!signal?.aborted) answer() })
    }))
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const client = newClient()
      client.setQueryData(queryKeys.currentUser(), reader)
      markSessionActive()
      Object.assign(server, { logout: unreachable, me: lapsed })
      const first = vi.fn()
      const failed = logoutAndResetAccount(client, logout, first).catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(SESSION_READ_LIMIT_MS)
      expect(first).toHaveBeenCalledExactlyOnceWith(false)
      expect(await failed).toMatchObject({ status: 0 })
      // The reader tries again, and this time the API answers.
      server.logout = ok({ status: 'success' })
      const retry = vi.fn()
      const retried = logoutAndResetAccount(client, logout, retry)
      await vi.advanceTimersByTimeAsync(0)
      expect(logoutPosts()).toBe(2)
      await retried
      expect(retry).toHaveBeenCalledExactlyOnceWith(true)
      expect(hasActiveSession()).toBe(false)
    } finally {
      stalled.resolve()
      await vi.advanceTimersByTimeAsync(0)
      vi.useRealTimers()
    }
  })

  it("starts a logout of its own for an account whose login was accepted while an earlier logout's request was out", async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    markSessionActive()
    // Each request answers when the case lets it: the earlier logout's first.
    const answers = [deferred<void>(), deferred<void>()]
    let posted = 0
    server.logout = (config) => heldUntil(answers[posted++]?.promise ?? Promise.resolve(), ok({ status: 'success' }))(config)
    const first = vi.fn()
    const earlier = logoutAndResetAccount(client, logout, first)
    await waitFor(() => expect(logoutPosts()).toBe(1))
    // Another account's login lands meanwhile and its identity is accepted (app/login/page.tsx's order); its reader
    // logs out before the earlier request answers. Joined to the earlier logout, theirs would end nothing.
    acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
    client.setQueryData(queryKeys.currentUser(), other)
    markSessionActive()
    const second = vi.fn()
    const later = logoutAndResetAccount(client, logout, second)
    await waitFor(() => expect(logoutPosts()).toBe(2))
    // The earlier logout ends first, its login gone, and leaves the later one running: a press now joins that one.
    answers[0].resolve()
    await earlier
    const again = vi.fn()
    const joined = logoutAndResetAccount(client, logout, again)
    answers[1].resolve()
    await Promise.all([later, joined])
    expect(logoutPosts()).toBe(2)
    expect(first).not.toHaveBeenCalled()
    expect(again).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledExactlyOnceWith(true)
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(hasActiveSession()).toBe(false)
  })

  it('offline, reports at once rather than holding the logout until the connection returns', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), reader)
    Object.assign(server, { logout: unreachable, me: unreachable })
    const continued = vi.fn()
    onlineManager.setOnline(false)
    await expect(logoutAndResetAccount(client, logout, continued)).rejects.toMatchObject({ status: 0 })
    expect(meReads()).toBe(1)
    expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE)
    expect(continued).toHaveBeenCalledWith(false)
  })
})
