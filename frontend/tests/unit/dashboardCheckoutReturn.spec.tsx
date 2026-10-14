import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'
import DashboardPage from '@/app/dashboard/page'

/**
 * What the dashboard says after Stripe's checkout, and the trial banner's plan wiring, rendered against a
 * mocked subscription snapshot with the REAL TrialBanner (BillingPanel.spec's style).
 *
 * - A plain visit says nothing about a checkout.
 * - `?success=true` says "Pro is active" only when the subscription query says Pro, and "Checkout finished"
 *   (a title, then "Your plan updates in a moment." as its description; a Notice title is one phrase, never
 *   two clauses joined by a semicolon, which noticeTitlesAreOnePhrase.spec.ts holds app-wide) only while it
 *   still says Free. The flag is then dropped from the address, so a second visit to the same page says nothing.
 * - The trial banner keys on the resolved plan (`subscription.is_pro`), never the /me `is_pro` mirror,
 *   which stays true on an expired trial remnant (lessons/frontend-trial-labels-use-entitlements.md). Its
 *   fixtures sit at midday UTC, so the date reads alike in any runner's zone (TrialBanner.spec pins the zone).
 */

const api = vi.hoisted(() => ({
  getCurrentUserSafe: vi.fn(),
  getUsage: vi.fn(),
  getSubscriptionStatus: vi.fn(),
  routerReplace: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe, logout: vi.fn() }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getUsage: api.getUsage,
  getSubscriptionStatus: api.getSubscriptionStatus,
  createPortalSession: vi.fn(),
}))
vi.mock('@/features/summaries/api/summaries-api', () => ({
  getSavedSummaries: () => Promise.resolve([]),
  deleteSavedSummary: vi.fn(),
}))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({
  getWatchlistInsights: () => Promise.resolve([]),
  addToWatchlist: vi.fn(),
  removeFromWatchlist: vi.fn(),
}))
vi.mock('@/features/companies/api/companies-api', () => ({ searchCompanies: vi.fn() }))
// router.replace moves the address as the real router does, so the next visit reads what is left.
const router = { push: vi.fn(), refresh: vi.fn(), replace: api.routerReplace }
vi.mock('next/navigation', () => ({ useRouter: () => router }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/lib/analytics', () => ({ default: { identify: vi.fn(), logout: vi.fn() } }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_CALENDAR: false,
}))
// The embedded feature widgets are not under test; TrialBanner is, so it stays real.
vi.mock('@/features/companies/components/CompanySearch', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/FilingFeed', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/EarningsCalendar', () => ({ default: () => null }))
vi.mock('@/features/dashboard/components/YourCompanies', () => ({ default: () => null }))

const user: CurrentUser = {
  id: 7, email: 'reader@example.com', full_name: 'Reader', is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}
const usage = { summaries_used: 1, summaries_limit: null, is_pro: true, month: '2026-10' } as Usage
const free: SubscriptionStatus = {
  is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null,
  plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false,
}
const pro: SubscriptionStatus = { ...free, is_pro: true, plan: 'pro', status: 'active', stripe_customer_id: 'cus_1' }

const PRO_ACTIVE = 'Pro is active'
const UPDATING = 'Checkout finished'
const UPDATING_DETAIL = 'Your plan updates in a moment. Reload this page if it still shows Free.'

async function renderDashboard(subscription: SubscriptionStatus, me: CurrentUser = user) {
  api.getCurrentUserSafe.mockResolvedValue(me)
  api.getUsage.mockResolvedValue(usage)
  api.getSubscriptionStatus.mockResolvedValue(subscription)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>)
  // The loaded page, past the skeleton.
  await screen.findByRole('heading', { name: 'Plan and usage' })
}

beforeEach(() => {
  api.routerReplace.mockImplementation((href: string) => window.history.replaceState(null, '', href))
})

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
  window.history.replaceState(null, '', '/')
})

describe('Dashboard after checkout', () => {
  it('says nothing about a checkout on a plain visit', async () => {
    window.history.replaceState(null, '', '/dashboard')
    await renderDashboard(pro)
    expect(screen.queryByText(PRO_ACTIVE)).not.toBeInTheDocument()
    expect(screen.queryByText(UPDATING)).not.toBeInTheDocument()
    expect(api.routerReplace).not.toHaveBeenCalled()
  })

  it('says the plan updates in a moment while the query still says Free, then drops the flag', async () => {
    window.history.replaceState(null, '', '/dashboard?success=true&tab=alerts')
    await renderDashboard(free)
    expect(await screen.findByText(UPDATING)).toBeInTheDocument()
    expect(screen.getByText(UPDATING_DETAIL)).toBeInTheDocument()
    expect(screen.queryByText(PRO_ACTIVE)).not.toBeInTheDocument()
    // Other params are kept; only the return flag goes.
    expect(api.routerReplace).toHaveBeenCalledWith('/dashboard?tab=alerts', { scroll: false })
    expect(window.location.search).toBe('?tab=alerts')

    // A second visit to the address left behind (a reload, a history entry) says nothing.
    cleanup()
    await renderDashboard(free)
    expect(screen.queryByText(UPDATING)).not.toBeInTheDocument()
    expect(screen.queryByText(UPDATING_DETAIL)).not.toBeInTheDocument()
    expect(screen.queryByText(PRO_ACTIVE)).not.toBeInTheDocument()
  })

  it('says Pro is active only when the query says Pro', async () => {
    window.history.replaceState(null, '', '/dashboard?success=true')
    await renderDashboard(pro)
    expect(await screen.findByText(PRO_ACTIVE)).toBeInTheDocument()
    expect(screen.queryByText(UPDATING)).not.toBeInTheDocument()
    expect(screen.queryByText(UPDATING_DETAIL)).not.toBeInTheDocument()
    expect(window.location.pathname + window.location.search).toBe('/dashboard')

    cleanup()
    await renderDashboard(pro)
    expect(screen.queryByText(PRO_ACTIVE)).not.toBeInTheDocument()
  })
})

describe('Dashboard trial banner (the real TrialBanner)', () => {
  it('shows no banner for an expired trial remnant, even while /me still mirrors is_pro', async () => {
    window.history.replaceState(null, '', '/dashboard')
    await renderDashboard({ ...free, status: 'trialing', trial_end: '2026-06-25T12:00:00Z' }, { ...user, is_pro: true })
    expect(screen.queryByText(/Your Pro trial ends/)).not.toBeInTheDocument()
  })

  it('states the end date of a live Pro trial', async () => {
    window.history.replaceState(null, '', '/dashboard')
    await renderDashboard({ ...pro, status: 'trialing', trial_end: '2026-06-25T12:00:00Z' })
    expect(screen.getByText('Your Pro trial ends Jun 25, 2026.')).toBeInTheDocument()
  })
})
