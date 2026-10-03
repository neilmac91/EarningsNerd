import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { SavedSummary } from '@/features/summaries/api/summaries-api'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'
import DashboardPage from '@/app/dashboard/page'

/**
 * The dashboard's two Retry buttons and the saved-summary Delete keep keyboard focus through their
 * own request, and hand it to a stable heading when their own success unmounts them.
 *
 * Retry: a failed query has no data, so its refetch puts it back to pending and the page-wide skeleton
 * used to replace the error card (or the plan strip) and the focused Retry with it. A pressed Retry
 * now keeps its failure until the refetch settles (lib/useRetainedFailure).
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
vi.mock('@/features/watchlist/api/watchlist-api', () => ({ getWatchlistInsights: api.getWatchlistInsights }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: api.routerPush, refresh: vi.fn() }) }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: api.toastError } }))
vi.mock('@/lib/analytics', () => ({ default: { identify: vi.fn(), logout: vi.fn() } }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_CALENDAR: false,
}))
// The page's own sections are under test; its embedded feature widgets are not.
vi.mock('@/features/subscriptions/components/TrialBanner', () => ({ default: () => null }))
vi.mock('@/features/companies/components/CompanySearch', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/FilingFeed', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/EarningsCalendar', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/YourCompanies', () => ({ default: () => null }))

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

function renderDashboard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>)
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
    // Still the error card, not the page skeleton: Retry is busy, focused, and refuses a second press.
    expect(screen.getByText('Unable to load your dashboard')).toBeInTheDocument()
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
})

describe('Saved summary Delete', () => {
  const apple = saved(1, 'Apple Inc.')
  const microsoft = saved(2, 'Microsoft Corp')

  it('deletes one at a time, stays busy until the refetch drops the row, then lands on the section heading', async () => {
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

    // Deleted, but the row is still on screen until saved summaries refetch: still busy, still
    // focused, and a second activation sends no second DELETE.
    await act(async () => del.resolve(undefined))
    await waitFor(() => expect(api.getSavedSummaries).toHaveBeenCalledTimes(2))
    await settle()
    expectBusyAndFocused(deleteApple)
    fireEvent.click(deleteApple)
    await settle()
    expect(api.deleteSavedSummary).toHaveBeenCalledTimes(1)

    await act(async () => refetched.resolve([microsoft]))
    await waitFor(() => expect(deleteApple.isConnected).toBe(false))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Saved summaries' }))
    expect(deleteMicrosoft).not.toHaveAttribute('aria-disabled')
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
