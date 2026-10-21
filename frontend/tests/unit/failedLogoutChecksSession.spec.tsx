import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import api from '@/lib/api/client'
import { logout, type CurrentUser } from '@/features/auth/api/auth-api'
import { LOGOUT_FAILED_MESSAGE, acceptLoginAndResetAccount, logoutAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getExplicitSessionGeneration, markSessionActive } from '@/lib/api/session'
import { refreshAccessToken } from '@/lib/api/refresh'
import { queryKeys } from '@/lib/queryKeys'
import Header from '@/components/Header'
import DashboardPage from '@/app/dashboard/page'

/**
 * A logout whose request fails (a network error, a 5xx, the API's 504) asks /me before it acts, from every control
 * that logs out: the site header's account menu, its mobile menu and the dashboard's own button. A user who comes
 * back means the logout did not take: the reader is told, nothing navigates, and the user shows again so they can
 * try again. No user (the API's 503 clears the session cookies) proceeds as a logout that succeeded. A read that
 * fails too reports the logout as not taken and stays put. The dashboard never leaves for /login on the null the
 * reset leaves while that read runs, whichever control started it. A login accepted meanwhile owns the tab.
 *
 * The requests run through the real API client and auth API, with the adapter answering, so the interceptor's
 * statuses, the session flag and the generation fences are the ones the app runs.
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

/** What the API answers: /me and the logout POST, each replaceable mid-test; every request is recorded. */
const server = { me: ok(reader), logout: ok({ status: 'success' }), requests: [] as string[] }
const meReads = () => server.requests.filter((request) => request === 'get /api/auth/me').length
const originalAdapter = api.defaults.adapter
const clients: QueryClient[] = []
const newClient = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  return client
}

beforeEach(() => {
  advanceSessionGeneration()
  clearSessionActive()
  server.me = ok(reader)
  server.logout = ok({ status: 'success' })
  server.requests = []
  api.defaults.adapter = async (config) => {
    server.requests.push(`${config.method} ${config.url}`)
    if (config.url === '/api/auth/me') return server.me(config)
    if (config.url === '/api/auth/logout') return server.logout(config)
    throw new Error(`unexpected request ${config.method} ${config.url}`)
  }
})
afterEach(() => {
  cleanup()
  clients.splice(0).forEach((client) => client.clear())
  api.defaults.adapter = originalAdapter
  vi.clearAllMocks()
})

/** Each control that logs out: what shows its page loaded and signed in, how to press it, where a successful
 *  logout goes, and what shows the reader still signed in afterwards. */
const CONTROLS = {
  'account menu': {
    render: () => render(<QueryClientProvider client={newClient()}><Header /></QueryClientProvider>),
    loaded: () => screen.findByRole('button', { name: 'Account menu' }),
    press: () => {
      fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
      fireEvent.click(screen.getByRole('menuitem', { name: 'Log out' }))
    },
    destination: '/',
    signedIn: () => screen.findByRole('button', { name: 'Account menu' }),
  },
  'mobile menu': {
    render: () => render(<QueryClientProvider client={newClient()}><Header /></QueryClientProvider>),
    loaded: () => screen.findByRole('button', { name: 'Account menu' }),
    press: () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
      fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
    },
    destination: '/',
    signedIn: async () => {
      fireEvent.click(await screen.findByRole('button', { name: 'Open menu' }))
      return screen.findByRole('button', { name: 'Log out' })
    },
  },
  dashboard: {
    render: () => render(<QueryClientProvider client={newClient()}><DashboardPage /></QueryClientProvider>),
    loaded: () => screen.findByText('Welcome back, Reader'),
    press: () => fireEvent.click(screen.getByRole('button', { name: 'Log out' })),
    destination: '/login',
    signedIn: () => screen.findByText('Welcome back, Reader'),
  },
} as const
const controls = Object.keys(CONTROLS) as (keyof typeof CONTROLS)[]

describe.each(controls)('a logout from the %s', (name) => {
  const control = CONTROLS[name]
  /** Render the signed-in page; once its first /me has answered, the API gives these answers, then the press. */
  const pressAfter = async (answers: { logout?: Answer; me?: Answer }) => {
    control.render()
    await control.loaded()
    Object.assign(server, answers)
    control.press()
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
  })

  it('answered 503 with the session cookies cleared proceeds as a logout that succeeded', async () => {
    await pressAfter({
      logout: status(503, 'This browser is logged out, but we could not end the session on the server.'),
      me: status(401, 'Could not validate credentials'),
    })
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith(control.destination))
    expect(meReads()).toBe(2)
    expect(nav.refresh).toHaveBeenCalledTimes(1)
    expect(toasts.error).not.toHaveBeenCalled()
    expect(tracked.logout).toHaveBeenCalledTimes(name === 'dashboard' ? 1 : 0)
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

  it('whose /me read fails too tells the reader and stays put', async () => {
    await pressAfter({ logout: unreachable, me: unreachable })
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await settle()
    expect(meReads()).toBe(2)
    expect(nav.push).not.toHaveBeenCalled()
    expect(nav.refresh).not.toHaveBeenCalled()
  })
})

describe('the dashboard while a failed logout reads /me', () => {
  it.each(['dashboard', 'site header'])('does not leave for /login, from the %s control, until /me has answered', async (from) => {
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
    // The reset left a null user and its read is in flight: the redirect waits for it.
    await waitFor(() => expect(meReads()).toBe(2))
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
    check.resolve(reader)
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await screen.findByText('Welcome back, Reader')
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
  })

  it('stays put when that read fails too', async () => {
    render(<QueryClientProvider client={newClient()}><DashboardPage /></QueryClientProvider>)
    await screen.findByText('Welcome back, Reader')
    Object.assign(server, { logout: unreachable, me: unreachable })
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }))
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE))
    await screen.findByText('Unable to load your dashboard')
    await settle()
    expect(nav.push).not.toHaveBeenCalled()
  })
})

describe('logoutAndResetAccount after a failed request', () => {
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
    try {
      await expect(logoutAndResetAccount(client, logout, continued)).rejects.toMatchObject({ status: 0 })
    } finally {
      onlineManager.setOnline(true)
    }
    expect(meReads()).toBe(1)
    expect(toasts.error).toHaveBeenCalledWith(LOGOUT_FAILED_MESSAGE)
    expect(continued).toHaveBeenCalledWith(false)
  })
})

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(file) : /\.tsx?$/.test(file) ? [file] : []
  })
}

describe('every control that logs out acts only on a logout that took', () => {
  it('each logoutAndResetAccount call hands it an inline continuation that returns at once on failure', () => {
    // A continuation that navigated on `false` would leave a reader who is still signed in believing they are not.
    // Read: every call by that name in the app's source, and any import that renames it (whose calls the walk could
    // not see). A continuation passed by reference is refused, since the walk cannot read it.
    const calls: string[] = []
    const errors: string[] = []
    for (const directory of ['app', 'components', 'features', 'hooks', 'lib']) {
      for (const file of sourceFiles(path.join(frontend, directory))) {
        const source = readFileSync(file, 'utf8')
        if (!source.includes('logoutAndResetAccount')) continue
        const relative = path.relative(frontend, file)
        const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
        const visit = (node: ts.Node) => {
          if (ts.isImportSpecifier(node) && node.propertyName?.text === 'logoutAndResetAccount') {
            errors.push(`${relative}: imports logoutAndResetAccount as ${node.name.text}`)
          }
          if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'logoutAndResetAccount') {
            calls.push(relative)
            const continuation = node.arguments[2]
            if (continuation) {
              const parameter = ts.isArrowFunction(continuation) ? continuation.parameters[0]?.name.getText(ast) : undefined
              const first = ts.isArrowFunction(continuation) && ts.isBlock(continuation.body) ? continuation.body.statements[0] : undefined
              const returnsOnFailure = parameter !== undefined && first !== undefined && ts.isIfStatement(first) &&
                first.expression.getText(ast) === `!${parameter}` && ts.isReturnStatement(first.thenStatement) &&
                first.thenStatement.expression === undefined && first.elseStatement === undefined
              if (!returnsOnFailure) errors.push(`${relative}: the continuation must open with \`if (!succeeded) return\``)
            }
          }
          ts.forEachChild(node, visit)
        }
        visit(ast)
      }
    }
    expect(errors).toEqual([])
    // The inventory: a new control that logs out joins this list, and the cases above.
    expect(calls.sort()).toEqual(['app/dashboard/page.tsx', 'components/Header.tsx', 'features/auth/components/UserMenu.tsx'])
  })
})
