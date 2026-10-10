import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { SavedSummary } from '@/features/summaries/api/summaries-api'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'
import DashboardPage from '@/app/dashboard/page'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The dashboard's Retry buttons (the account card, the plan strip, Your companies) and the saved-summary
 * Delete keep keyboard focus through their own request, and hand it to a stable heading when they unmount
 * while they hold it.
 *
 * Retry: a failed query has no data, so any refetch (a press, a reconnect, an invalidation) puts it back to
 * pending, and the page-wide skeleton used to replace the error card (or the plan strip) and the focused
 * Retry with it. A failure the page has shown now stays up through any refetch until data replaces it
 * (hooks/useRetainedFailure.tsx), its RetryButton busy; a RetryButton that unmounts while it holds focus,
 * for any reason, hands focus to its heading. Nothing is armed by a press.
 *
 * Delete: aria-disabled + aria-busy + an early return while a delete is in flight, never native
 * `disabled`. It stays pending until the refetch drops the row, since the kept focus could otherwise
 * send a second DELETE (lessons/frontend-busy-controls-stay-focusable.md, rules (f) and (g)).
 *
 * Manage subscription stays pending until the page leaves for Stripe, as BillingPanel's Manage billing.
 */

const api = vi.hoisted(() => ({
  getCurrentUserSafe: vi.fn(),
  logout: vi.fn(),
  getUsage: vi.fn(),
  getSubscriptionStatus: vi.fn(),
  createPortalSession: vi.fn(),
  getSavedSummaries: vi.fn(),
  deleteSavedSummary: vi.fn(),
  getWatchlistInsights: vi.fn(),
  removeFromWatchlist: vi.fn(),
  routerPush: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe, logout: api.logout }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getUsage: api.getUsage,
  getSubscriptionStatus: api.getSubscriptionStatus,
  createPortalSession: api.createPortalSession,
}))
vi.mock('@/features/summaries/api/summaries-api', () => ({
  getSavedSummaries: api.getSavedSummaries,
  deleteSavedSummary: api.deleteSavedSummary,
}))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({
  getWatchlistInsights: api.getWatchlistInsights,
  addToWatchlist: vi.fn(),
  removeFromWatchlist: api.removeFromWatchlist,
}))
vi.mock('@/features/companies/api/companies-api', () => ({ searchCompanies: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: api.routerPush, refresh: vi.fn() }) }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: api.toastError } }))
vi.mock('@/lib/analytics', () => ({
  default: { identify: vi.fn(), logout: vi.fn(), watchlistAdded: vi.fn(), watchlistRemoved: vi.fn() },
}))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_CALENDAR: false,
}))
// The page's own sections and Your companies (whose Retry runs on the page's retained failure) are
// under test; the other embedded feature widgets are not.
vi.mock('@/features/subscriptions/components/TrialBanner', () => ({ default: () => null }))
vi.mock('@/features/companies/components/CompanySearch', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/FilingFeed', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/EarningsCalendar', () => ({ default: () => null }))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

/** TanStack starts fetches and notifies observers a few ticks after the call, so a request count or
    a busy flag is only meaningful once pending work has flushed. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

const user: CurrentUser = {
  id: 7, email: 'reader@example.com', full_name: 'Reader', is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}
const usage: Usage = {
  summaries_used: 1, summaries_limit: 3, is_pro: false, month: '2026-10',
  qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3,
} as Usage
const subscription: SubscriptionStatus = {
  is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null,
  plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false,
}
const saved = (id: number, name: string): SavedSummary => ({
  id,
  summary_id: id * 10,
  notes: null,
  created_at: '2026-09-01T00:00:00Z',
  summary: { id: id * 10, filing_id: id * 100 },
  filing: { id: id * 100, filing_type: '10-Q', filing_date: '2026-08-01', period_end_date: null },
  company: { id, ticker: name.slice(0, 4).toUpperCase(), name },
})

function renderDashboard(client = newClient()) {
  return { client, ...render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>) }
}
function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
}

/** Every query resolves unless a case overrides it. */
function healthyApi() {
  api.getCurrentUserSafe.mockResolvedValue(user)
  api.getUsage.mockResolvedValue(usage)
  api.getSubscriptionStatus.mockResolvedValue(subscription)
  api.getSavedSummaries.mockResolvedValue([])
  api.getWatchlistInsights.mockResolvedValue([])
}

/** Busy is announced and the control keeps focus. That a busy flag never turns it natively disabled
    is the rule-12 gate's job (busyControlsStayFocusable.spec.ts). */
function expectBusyAndFocused(control: HTMLElement) {
  expect(control.isConnected).toBe(true)
  expect(control).toHaveAttribute('aria-busy', 'true')
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(document.activeElement).toBe(control)
}

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

afterEach(() => onlineManager.setOnline(true))

const title = () => screen.getByRole('heading', { level: 1, name: 'Dashboard' })

describe('Nothing takes focus the user did not lose', () => {
  it('a cold load moves no focus', async () => {
    healthyApi()
    api.getSavedSummaries.mockResolvedValue([saved(1, 'Apple Inc.')])
    renderDashboard()
    await screen.findByRole('heading', { name: 'Saved summaries' })
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it('a mount over a warm cache (the dashboard renders at once) moves no focus', async () => {
    healthyApi()
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), user)
    client.setQueryData(queryKeys.usage.byUser(user.id), usage)
    client.setQueryData(queryKeys.subscription.byUser(user.id), subscription)
    client.setQueryData(queryKeys.savedSummaries(), [saved(1, 'Apple Inc.')])
    renderDashboard(client)
    expect(screen.getByRole('heading', { name: 'Plan and usage' })).toBeInTheDocument()
    await settle()
    expect(document.activeElement).toBe(document.body)
  })
})

describe('Dashboard Retry (the account could not load)', () => {
  it('keeps the error card and its focused Retry through the retry, then hands focus to the page title', async () => {
    healthyApi()
    const refetched = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('Server unavailable')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2))
    await settle()
    // Still the error card, with its error, not the page skeleton: Retry is busy, focused, and refuses
    // a second press.
    expect(screen.getByText('Unable to load your dashboard')).toBeInTheDocument()
    expect(screen.getByText('Server unavailable')).toBeInTheDocument()
    expectBusyAndFocused(retry)
    fireEvent.click(retry)
    await settle()
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2)

    await act(async () => refetched.resolve(user))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1, name: 'Dashboard' })))
  })

  it('a retry that fails again leaves the keyboard user on Retry, live again', async () => {
    healthyApi()
    const refetched = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('Server unavailable')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))

    await act(async () => refetched.reject(new Error('Still unavailable')))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(retry.isConnected).toBe(true)
    expect(retry).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(retry)
    expect(screen.getByText('Still unavailable')).toBeInTheDocument()
  })

  it('after a retry that failed again and the user moved off it, a recovery nobody pressed moves no focus', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('Server unavailable')).mockRejectedValueOnce(new Error('Still unavailable'))
    const { client } = renderDashboard()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await screen.findByText('Still unavailable')
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    retry.blur()

    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await screen.findByRole('heading', { level: 1, name: 'Dashboard' })
    await screen.findByRole('heading', { name: 'Plan and usage' })
    await settle()
    expect(document.activeElement).toBe(document.body)
  })
})

describe('Plan and usage Retry', () => {
  it('keeps the plan strip and its focused Retry through the retry, then hands focus to the strip heading', async () => {
    healthyApi()
    const refetched = deferred<Usage>()
    api.getUsage.mockRejectedValueOnce(new Error('usage down')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const alert = await screen.findByRole('alert')
    const retry = within(alert).getByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getUsage).toHaveBeenCalledTimes(2))
    await settle()
    // The dashboard stays up (no page-wide skeleton), and Retry is busy, focused, and inert.
    expect(screen.getByText('Unable to load plan details')).toBeInTheDocument()
    expect(screen.getByText('Jump to any company')).toBeInTheDocument()
    expectBusyAndFocused(retry)
    fireEvent.click(retry)
    await settle()
    expect(api.getUsage).toHaveBeenCalledTimes(2)

    await act(async () => refetched.resolve(usage))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(screen.getByText('1 / 3 summaries')).toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Plan and usage' })))
  })

  it('a retry that fails again leaves the keyboard user on Retry, live again', async () => {
    healthyApi()
    const refetched = deferred<SubscriptionStatus>()
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('billing down')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))

    await act(async () => refetched.reject(new Error('billing still down')))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(retry.isConnected).toBe(true)
    expect(retry).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(retry)
  })

  it('retries only the query that failed, so a healthy sibling cannot settle the strip early', async () => {
    healthyApi()
    const refetched = deferred<Usage>()
    api.getUsage.mockRejectedValueOnce(new Error('usage down')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    const subscriptionCalls = api.getSubscriptionStatus.mock.calls.length
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getUsage).toHaveBeenCalledTimes(2))
    await settle()
    expect(api.getSubscriptionStatus).toHaveBeenCalledTimes(subscriptionCalls)
    expectBusyAndFocused(retry)

    await act(async () => refetched.resolve(usage))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(api.getSubscriptionStatus).toHaveBeenCalledTimes(subscriptionCalls)
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Plan and usage' })))
  })

  it('with both failed, the strip and its Retry stay until both retries settle; one failing again keeps focus there', async () => {
    healthyApi()
    const usageRefetched = deferred<Usage>()
    const subscriptionRefetched = deferred<SubscriptionStatus>()
    api.getUsage.mockRejectedValueOnce(new Error('usage down')).mockReturnValueOnce(usageRefetched.promise)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('billing down')).mockReturnValueOnce(subscriptionRefetched.promise)
    renderDashboard()

    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getSubscriptionStatus).toHaveBeenCalledTimes(2))

    // Usage recovers first: the subscription retry is still running, so nothing has recovered yet.
    await act(async () => usageRefetched.resolve(usage))
    await settle()
    expectBusyAndFocused(retry)
    expect(screen.getByText('Unable to load plan details')).toBeInTheDocument()

    await act(async () => subscriptionRefetched.reject(new Error('billing still down')))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(retry.isConnected).toBe(true)
    expect(document.activeElement).toBe(retry)
  })

  it('a mouse user who moved on keeps their focus when the retry succeeds', async () => {
    healthyApi()
    const refetched = deferred<Usage>()
    api.getUsage.mockRejectedValueOnce(new Error('usage down')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    fireEvent.click(retry)
    const logOut = screen.getByRole('button', { name: 'Log out' })
    logOut.focus()
    await act(async () => refetched.resolve(usage))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(logOut)
  })

  it('after a retry that failed again and the user moved off it, a recovery nobody pressed moves no focus', async () => {
    healthyApi()
    api.getUsage.mockRejectedValueOnce(new Error('usage down')).mockRejectedValueOnce(new Error('usage still down'))
    const { client } = renderDashboard()

    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getUsage).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(retry.isConnected).toBe(true)
    retry.blur()

    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.usage.byUser(user.id) }) })
    await screen.findByText('1 / 3 summaries')
    await settle()
    expect(document.activeElement).toBe(document.body)
  })
})

describe('Your companies Retry', () => {
  const errorCard = async () => {
    await screen.findByText('Unable to load your companies')
    return screen.getByRole('button', { name: 'Retry' })
  }

  it('keeps the error card and its focused Retry through the retry, then hands focus to "Your companies"', async () => {
    healthyApi()
    const refetched = deferred<unknown[]>()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = await errorCard()
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2))
    await settle()
    // Still the error card, not the section's skeleton: Retry is busy, focused, and inert.
    expect(screen.getByText('Unable to load your companies')).toBeInTheDocument()
    expectBusyAndFocused(retry)
    fireEvent.click(retry)
    await settle()
    expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2)

    await act(async () => refetched.resolve([]))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(screen.getByText('No companies yet')).toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Your companies' })))
  })

  it('after a retry that failed again and the user moved off it, a recovery nobody pressed moves no focus', async () => {
    healthyApi()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down')).mockRejectedValueOnce(new Error('still down'))
    const { client } = renderDashboard()

    const retry = await errorCard()
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(retry.isConnected).toBe(true)
    expect(document.activeElement).toBe(retry)
    retry.blur()

    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.watchlistInsights() }) })
    await screen.findByText('No companies yet')
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it('a pointer retry that fails again moves no focus', async () => {
    healthyApi()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down')).mockRejectedValueOnce(new Error('still down'))
    renderDashboard()

    const retry = await errorCard()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it('a remove whose insights refetch fails leaves no live remove button for the removed row', async () => {
    healthyApi()
    const row = (id: number, ticker: string, name: string) => ({ company: { id, ticker, name }, latest_filing: null, total_filings: 0 })
    api.removeFromWatchlist.mockResolvedValue(undefined)
    api.getWatchlistInsights
      .mockReset()
      .mockResolvedValueOnce([row(1, 'AAPL', 'Apple Inc.'), row(2, 'MSFT', 'Microsoft Corp')])
      .mockRejectedValueOnce(new Error('insights down'))
    renderDashboard()

    const removeApple = await screen.findByRole('button', { name: /Remove Apple.* from watchlist/ })
    removeApple.focus()
    fireEvent.click(removeApple)
    await waitFor(() => expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2))
    await settle()
    // The page reads the failed refetch as an error, so the section's error card replaces the list:
    // the removed row's button cannot go live again, and no cache prune is needed.
    expect(screen.queryByRole('button', { name: /Remove Apple.* from watchlist/ })).not.toBeInTheDocument()
    expect(screen.getByText('Unable to load your companies')).toBeInTheDocument()
    expect(api.removeFromWatchlist).toHaveBeenCalledTimes(1)
  })

  it('a mouse user who moved on keeps their focus when the retry succeeds', async () => {
    healthyApi()
    const refetched = deferred<unknown[]>()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down')).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const retry = await errorCard()
    fireEvent.click(retry)
    const logOut = screen.getByRole('button', { name: 'Log out' })
    logOut.focus()
    await act(async () => refetched.resolve([]))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(logOut)
  })
})

describe('Dashboard Retry through refetches nobody pressed, and offline', () => {
  it('account card: a press paused offline is busy and inert, does not redirect, and a second press sends nothing', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    await settle()
    expectBusyAndFocused(retry)
    fireEvent.click(retry)
    await settle()
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(1)
    expect(api.routerPush).not.toHaveBeenCalled()

    // Back online the paused fetch runs once and fails: the card and its Retry stay, live, focused.
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2)
    expect(document.activeElement).toBe(retry)
  })

  it('account card: a refetch nobody pressed keeps the card and the focused Retry busy; its success hands focus to the title', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    const { client } = renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    const background = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await settle()
    expectBusyAndFocused(retry)
    expect(screen.getByText('Unable to load your dashboard')).toBeInTheDocument()
    await act(async () => background.resolve(user))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(title())
  })

  it('account card: a reconnect refetch keeps the card mounted, then hands focus to the title', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    act(() => onlineManager.setOnline(false))
    const background = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValueOnce(background.promise)
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2))
    expectBusyAndFocused(retry)
    await act(async () => background.resolve(user))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(title())
  })

  it('account card: two presses offline, a failure, then a recovery nobody pressed leaves a user who moved off on <body>', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    const { client } = renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    fireEvent.click(retry)
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2)
    retry.blur()
    act(() => { void client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await screen.findByRole('heading', { name: 'Plan and usage' })
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it('plan strip: a reconnect refetch keeps the strip (not the page skeleton) and the focused Retry busy; its success hands focus off', async () => {
    healthyApi()
    api.getUsage.mockRejectedValueOnce(new Error('usage down'))
    renderDashboard()
    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    act(() => onlineManager.setOnline(false))
    const background = deferred<Usage>()
    api.getUsage.mockReturnValueOnce(background.promise)
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(api.getUsage).toHaveBeenCalledTimes(2))
    expectBusyAndFocused(retry)
    expect(screen.getByText('Jump to any company')).toBeInTheDocument()
    await act(async () => background.resolve(usage))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Plan and usage' }))
  })

  it('plan strip: a press offline is busy, and two presses send one request', async () => {
    healthyApi()
    api.getUsage.mockRejectedValueOnce(new Error('usage down'))
    renderDashboard()
    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    await settle()
    expectBusyAndFocused(retry)
    fireEvent.click(retry)
    api.getUsage.mockResolvedValueOnce(usage)
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(api.getUsage).toHaveBeenCalledTimes(2)
  })

  it('plan strip: two presses offline, a failure, then a recovery nobody pressed moves nothing', async () => {
    healthyApi()
    const resumed = deferred<Usage>()
    api.getUsage.mockRejectedValueOnce(new Error('usage down')).mockReturnValueOnce(resumed.promise).mockResolvedValue(usage)
    const { client } = renderDashboard()
    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    act(() => onlineManager.setOnline(false))
    fireEvent.click(retry)
    await settle()
    fireEvent.click(retry)
    await settle()
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(api.getUsage).toHaveBeenCalledTimes(2))
    await act(async () => resumed.reject(new Error('still down')))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(document.activeElement).toBe(retry)
    retry.blur()
    act(() => { void client.refetchQueries({ queryKey: queryKeys.usage.all() }) })
    await screen.findByText('1 / 3 summaries')
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it('Your companies: an invalidation (a watchlist change) keeps the card and the focused Retry busy; its success hands focus off', async () => {
    healthyApi()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down'))
    const { client } = renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    const background = deferred<unknown[]>()
    api.getWatchlistInsights.mockReturnValueOnce(background.promise)
    act(() => { void client.invalidateQueries({ queryKey: queryKeys.watchlistInsights() }) })
    await settle()
    expectBusyAndFocused(retry)
    expect(screen.getByText('Unable to load your companies')).toBeInTheDocument()
    await act(async () => background.resolve([]))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Your companies' }))
  })

  it('Your companies: a press offline is busy and focused', async () => {
    healthyApi()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down'))
    renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    await settle()
    expectBusyAndFocused(retry)
  })

  it('Your companies: a paused press whose fetch fails inside one notify batch, then a recovery nobody pressed, moves nothing', async () => {
    healthyApi()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down'))
    const { client } = renderDashboard()
    const retry = await screen.findByRole('button', { name: 'Retry' })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    await settle()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('insights down'))
    act(() => onlineManager.setOnline(true))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    retry.blur()
    act(() => { void client.refetchQueries({ queryKey: queryKeys.watchlistInsights() }) })
    await waitFor(() => expect(screen.queryByText('Unable to load your companies')).not.toBeInTheDocument())
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it('Your companies: one paused press, an instant failure on resume, then a reconnect recovery leaves focus on <body>', async () => {
    const settle3 = async () => { await settle(); await settle(); await settle() }
    healthyApi()
    api.getWatchlistInsights.mockRejectedValue(new Error('insights down'))
    renderDashboard()
    await settle3()
    onlineManager.setOnline(false)
    api.getWatchlistInsights.mockReset()
    api.getWatchlistInsights.mockImplementation(() => Promise.reject(new Error('again')))
    const retry = screen.getByRole('button', { name: /^Retry$/ })
    retry.focus()
    fireEvent.click(retry)
    await settle3()
    act(() => onlineManager.setOnline(true))
    await settle3()
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await settle3()
    expect(screen.getByText('Unable to load your companies')).toBeInTheDocument()
    act(() => retry.blur())
    const recovered = deferred<never[]>()
    api.getWatchlistInsights.mockReset()
    api.getWatchlistInsights.mockReturnValue(recovered.promise)
    act(() => { onlineManager.setOnline(false); onlineManager.setOnline(true) })
    await settle3()
    await act(async () => recovered.resolve([]))
    await settle3()
    expect(screen.getByText('No companies yet')).toBeInTheDocument()
    expect(document.activeElement).toBe(document.body)
  })

  it('a cold load offline shows the skeleton, not a blank page or a /login redirect', async () => {
    healthyApi()
    onlineManager.setOnline(false)
    renderDashboard()
    await settle()
    expect(api.routerPush).not.toHaveBeenCalled()
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    expect(title()).toBeInTheDocument()
  })
})

describe('Retry announcements', () => {
  it('a refetch nobody pressed makes Retry busy under its own label, so its alert has nothing new to say', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    const { client } = renderDashboard()
    const alert = await screen.findByRole('alert')
    const retry = within(alert).getByRole('button', { name: 'Retry' })
    const said = alert.textContent
    const background = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    // Busy in every way but its words: aria-busy, aria-disabled, the spinner, a refused press.
    expect(retry).toHaveAttribute('aria-disabled', 'true')
    expect(retry.querySelector('svg')).not.toBeNull()
    expect(retry).toHaveAccessibleName('Retry')
    expect(alert.textContent).toBe(said)
    fireEvent.click(retry)
    await settle()
    expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2)

    await act(async () => background.reject(new Error('account down')))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(alert.textContent).toBe(said)
  })

  it('its own press reads "Retrying…" while the press runs and "Retry" when it fails again; a later refetch nobody pressed keeps "Retry"', async () => {
    healthyApi()
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('account down'))
    const { client } = renderDashboard()
    const retry = within(await screen.findByRole('alert')).getByRole('button', { name: 'Retry' })
    retry.focus()
    const pressed = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValueOnce(pressed.promise)
    fireEvent.click(retry)
    expect(retry).toHaveAccessibleName('Retrying…')
    await act(async () => pressed.reject(new Error('account down')))
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    expect(retry).toHaveAccessibleName('Retry')

    const background = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    expect(retry).toHaveAccessibleName('Retry')
    await act(async () => background.resolve(user))
    await waitFor(() => expect(retry.isConnected).toBe(false))
  })
})

describe('Manage subscription', () => {
  it('stays busy while the page leaves for the portal, and is live again after a back-forward restore', async () => {
    healthyApi()
    api.getSubscriptionStatus.mockResolvedValue({ ...subscription, is_pro: true, plan: 'pro', status: 'active' })
    api.createPortalSession.mockResolvedValue({ url: 'https://billing.stripe.com/p/session_1' })
    // jsdom cannot navigate; a plain object records the assignment instead.
    const realLocation = window.location
    Object.defineProperty(window, 'location', { value: { href: '' }, writable: true, configurable: true })
    try {
      renderDashboard()
      const manage = await screen.findByRole('button', { name: 'Manage subscription' })
      manage.focus()
      fireEvent.click(manage)
      await waitFor(() => expect(window.location.href).toBe('https://billing.stripe.com/p/session_1'))
      await settle()
      // Still on the page while the browser leaves: busy, focused, and a second click opens nothing.
      expectBusyAndFocused(manage)
      fireEvent.click(manage)
      await settle()
      expect(api.createPortalSession).toHaveBeenCalledTimes(1)

      // Back from Stripe via the back-forward cache: pageshow settles the request.
      await act(async () => { window.dispatchEvent(new Event('pageshow')) })
      await waitFor(() => expect(manage).not.toHaveAttribute('aria-busy'))
      expect(manage).not.toHaveAttribute('aria-disabled')
      expect(document.activeElement).toBe(manage)
    } finally {
      Object.defineProperty(window, 'location', { value: realLocation, writable: true, configurable: true })
    }
  })

  it('a portal response with no URL says so and leaves the button live and focused', async () => {
    healthyApi()
    api.getSubscriptionStatus.mockResolvedValue({ ...subscription, is_pro: true, plan: 'pro', status: 'active' })
    api.createPortalSession.mockResolvedValue({ url: '' })
    renderDashboard()

    const manage = await screen.findByRole('button', { name: 'Manage subscription' })
    manage.focus()
    fireEvent.click(manage)
    await waitFor(() => expect(api.toastError).toHaveBeenCalledWith('Could not open the billing portal. Please try again.'))
    await waitFor(() => expect(manage).not.toHaveAttribute('aria-busy'))
    expect(manage).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(manage)
  })
})

describe('Saved summary Delete', () => {
  const apple = saved(1, 'Apple Inc.')
  const microsoft = saved(2, 'Microsoft Corp')

  it('deletes one at a time, busy and focused until the DELETE lands, then the row goes and focus lands on the heading', async () => {
    healthyApi()
    const del = deferred<void>()
    api.deleteSavedSummary.mockReturnValue(del.promise)
    const refetched = deferred<SavedSummary[]>()
    api.getSavedSummaries.mockReset()
    api.getSavedSummaries.mockResolvedValueOnce([apple, microsoft]).mockReturnValueOnce(refetched.promise)
    renderDashboard()

    const deleteApple = await screen.findByRole('button', { name: /Delete summary for Apple/ })
    const deleteMicrosoft = screen.getByRole('button', { name: /Delete summary for Microsoft/ })
    deleteApple.focus()
    fireEvent.click(deleteApple)
    await waitFor(() => expect(deleteApple).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(deleteApple)
    expect(deleteMicrosoft).toHaveAttribute('aria-disabled', 'true')
    expect(deleteMicrosoft).not.toHaveAttribute('aria-busy')
    fireEvent.click(deleteApple)
    fireEvent.click(deleteMicrosoft)
    await settle()
    expect(api.deleteSavedSummary).toHaveBeenCalledTimes(1)
    expect(api.deleteSavedSummary.mock.calls[0][0]).toBe(1)

    // The DELETE lands: the row goes at once, before the refetch answers, so there is no window in
    // which the deleted row's Delete is live. Focus lands on the section heading.
    await act(async () => del.resolve(undefined))
    await waitFor(() => expect(deleteApple.isConnected).toBe(false))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Saved summaries' }))
    expect(deleteMicrosoft).not.toHaveAttribute('aria-disabled')
    expect(api.getSavedSummaries).toHaveBeenCalledTimes(2)
    await act(async () => refetched.resolve([microsoft]))
    expect(api.deleteSavedSummary).toHaveBeenCalledTimes(1)
  })

  it('a refetch that fails after the DELETE does not bring the deleted row (or a live Delete) back', async () => {
    healthyApi()
    api.deleteSavedSummary.mockResolvedValue(undefined)
    api.getSavedSummaries.mockReset()
    api.getSavedSummaries.mockResolvedValueOnce([apple, microsoft]).mockRejectedValueOnce(new Error('list down'))
    renderDashboard()

    const deleteApple = await screen.findByRole('button', { name: /Delete summary for Apple/ })
    deleteApple.focus()
    fireEvent.click(deleteApple)
    await waitFor(() => expect(api.getSavedSummaries).toHaveBeenCalledTimes(2))
    await settle()
    expect(screen.queryByRole('button', { name: /Delete summary for Apple/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Delete summary for Microsoft/ })).toBeInTheDocument()
    expect(api.deleteSavedSummary).toHaveBeenCalledTimes(1)
  })

  it('deleting the last summary removes the section and lands on the Plan and usage heading', async () => {
    healthyApi()
    api.deleteSavedSummary.mockResolvedValue(undefined)
    api.getSavedSummaries.mockReset()
    api.getSavedSummaries.mockResolvedValueOnce([apple]).mockResolvedValueOnce([])
    renderDashboard()

    const deleteApple = await screen.findByRole('button', { name: /Delete summary for Apple/ })
    deleteApple.focus()
    fireEvent.click(deleteApple)
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Saved summaries' })).not.toBeInTheDocument())
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Plan and usage' }))
  })

  it('a failed delete keeps the row and the keyboard user on its button, live again', async () => {
    healthyApi()
    const del = deferred<void>()
    api.deleteSavedSummary.mockReturnValue(del.promise)
    api.getSavedSummaries.mockReset()
    api.getSavedSummaries.mockResolvedValue([apple])
    renderDashboard()

    const deleteApple = await screen.findByRole('button', { name: /Delete summary for Apple/ })
    deleteApple.focus()
    fireEvent.click(deleteApple)
    await waitFor(() => expect(deleteApple).toHaveAttribute('aria-busy', 'true'))

    await act(async () => del.reject(new Error('Delete failed')))
    await waitFor(() => expect(deleteApple).not.toHaveAttribute('aria-busy'))
    expect(deleteApple).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(deleteApple)
    expect(api.toastError).toHaveBeenCalledWith('Delete failed')
  })

  it('a mouse delete that moved focus elsewhere is not pulled back to the heading', async () => {
    healthyApi()
    api.deleteSavedSummary.mockResolvedValue(undefined)
    api.getSavedSummaries.mockReset()
    api.getSavedSummaries.mockResolvedValueOnce([apple, microsoft]).mockResolvedValueOnce([microsoft])
    renderDashboard()

    const deleteApple = await screen.findByRole('button', { name: /Delete summary for Apple/ })
    const elsewhere = screen.getByRole('link', { name: /Microsoft/ })
    fireEvent.click(deleteApple)
    elsewhere.focus()
    await waitFor(() => expect(deleteApple.isConnected).toBe(false))
    expect(document.activeElement).toBe(elsewhere)
  })
})
