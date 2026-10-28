import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import analytics from '@/lib/analytics'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import type { NotificationPreferences } from '@/features/notifications/api/notifications-api'
import { resetAccountQueries } from '@/features/auth/lib/accountQueryState'
import { queryKeys } from '@/lib/queryKeys'
import CompanyPageClient from '@/app/company/[ticker]/page-client'
import NotificationPreferencesForm from '@/features/settings/components/NotificationPreferencesForm'

/**
 * A mutation's answer belongs to the account that pressed it (E29): an answer that lands after the session generation
 * moved on (a logout, another login, a lost session) writes nothing into the next account's cache and says nothing to
 * its reader. The reset (resetAccountQueries) removes the account families before the next account reads them; a late
 * write would start that account's snapshot with this one's data. Here the company page's watchlist star (its rollback,
 * its toasts and analytics) and the alert preferences' save; the bell's mark-seen case and the structural gate that
 * every write into an account-owned family is fenced are in tests/unit/accountQueryState.spec.tsx.
 */

const api = vi.hoisted(() => ({
  addToWatchlist: vi.fn(),
  removeFromWatchlist: vi.fn(),
  getWatchlist: vi.fn(),
  getCompany: vi.fn(),
  getCompanyFilings: vi.fn(),
  getSummary: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({
  addToWatchlist: api.addToWatchlist,
  removeFromWatchlist: api.removeFromWatchlist,
  getWatchlist: api.getWatchlist,
}))
vi.mock('@/features/companies/api/companies-api', () => ({ getCompany: api.getCompany }))
vi.mock('@/features/filings/api/filings-api', () => ({ getCompanyFilings: api.getCompanyFilings }))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getSummary: api.getSummary }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/features/notifications/api/notifications-api', () => ({
  getNotificationPreferences: api.getNotificationPreferences,
  updateNotificationPreferences: api.updateNotificationPreferences,
}))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_FINANCIAL_CHARTS: false,
  ENABLE_INSIDER_ACTIVITY: false,
}))
vi.mock('@/lib/analytics', () => ({
  default: { watchlistAdded: vi.fn(), watchlistRemoved: vi.fn(), companyViewed: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('next/navigation', () => ({
  useParams: () => ({ ticker: 'aapl' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/company/aapl',
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) }
}

/** Lets the mutation's callbacks, which TanStack runs a few microtasks after its answer, finish. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

const watchlistItem = (id: number, ticker: string): WatchlistItem => ({
  id,
  company_id: id,
  created_at: '2026-01-01T00:00:00Z',
  company: { id, ticker, name: `${ticker} Inc.` },
})

const preferences = (changes: Partial<NotificationPreferences> = {}): NotificationPreferences => ({
  notify_10k: true, notify_10q: false, notify_8k: false, notify_20f: false, notify_6k: false,
  channel: 'email', digest: 'daily', realtime: false, realtime_available: true, eightk_available: false,
  ...changes,
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('a mutation answer that lands after the account changed (E29)', () => {
  const company: Company = { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.' }
  const filings: Filing[] = [
    {
      id: 11,
      filing_type: '10-K',
      filing_date: '2025-10-31',
      report_date: '2025-09-27',
      accession_number: '0000320193-25-000079',
      document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
      sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
    },
  ]

  it.each(['fails', 'succeeds'] as const)(
    "a watchlist star that %s after another account signs in leaves that account's watchlist alone and tells its reader nothing",
    async (outcome) => {
      api.getCompany.mockResolvedValue(company)
      api.getCompanyFilings.mockResolvedValue(filings)
      api.getSummary.mockResolvedValue(null)
      api.getCurrentUserSafe.mockResolvedValue({ id: 1, email: 'a@example.test' })
      api.getWatchlist.mockResolvedValue([watchlistItem(2, 'MSFT')])
      const answer = deferred<WatchlistItem>()
      api.addToWatchlist.mockReturnValue(answer.promise)
      const { client, unmount } = renderWithClient(<CompanyPageClient initialCompany={company} initialFilings={filings} />)

      const star = await screen.findByRole('button', { name: 'Add to watchlist' })
      await waitFor(() => expect(api.getWatchlist).toHaveBeenCalledTimes(1))
      fireEvent.click(star)
      await waitFor(() => expect(api.addToWatchlist).toHaveBeenCalledWith('AAPL'))

      // The first account leaves the page and logs out; the next signs in and reads its own list.
      unmount()
      resetAccountQueries(client)
      client.setQueryData(queryKeys.currentUser(), { id: 2, email: 'b@example.test' })
      const next = [watchlistItem(3, 'GOOG')]
      client.setQueryData(queryKeys.watchlist(), next)

      await act(async () => (outcome === 'fails' ? answer.reject(new Error('Network Error')) : answer.resolve(watchlistItem(4, 'AAPL'))))
      await settle()
      // Unfenced, a failure rolled the list back to the first account's [MSFT], and either answer toasted its star.
      expect(client.getQueryData(queryKeys.watchlist())).toEqual(next)
      expect(toast.error).not.toHaveBeenCalled()
      expect(toast.success).not.toHaveBeenCalled()
      expect(analytics.watchlistAdded).not.toHaveBeenCalled()
    },
  )

  it("an alert preferences save that answers after another account signs in leaves that account's preferences alone", async () => {
    api.getNotificationPreferences.mockResolvedValue(preferences())
    const saved = deferred<NotificationPreferences>()
    api.updateNotificationPreferences.mockReturnValue(saved.promise)
    const { client, unmount } = renderWithClient(<NotificationPreferencesForm />)

    fireEvent.click(await screen.findByRole('switch', { name: 'Quarterly reports (10-Q)' }))
    // TanStack passes the mutation function its context as a second argument.
    await waitFor(() => expect(api.updateNotificationPreferences.mock.calls[0]?.[0]).toEqual({ notify_10q: true }))

    unmount()
    resetAccountQueries(client)
    const next = preferences({ notify_10k: false, realtime: true })
    client.setQueryData(queryKeys.notificationPreferences(), next)

    await act(async () => saved.resolve(preferences({ notify_10q: true })))
    await settle()
    // Unfenced, the save wrote the first account's preferences, 10-Q on and 10-K on, over the next account's.
    expect(client.getQueryData(queryKeys.notificationPreferences())).toEqual(next)
  })

  it('in-account answers still land: the star rolls back on a failure, and a saved change shows the server\'s preferences', async () => {
    api.getCompany.mockResolvedValue(company)
    api.getCompanyFilings.mockResolvedValue(filings)
    api.getSummary.mockResolvedValue(null)
    api.getCurrentUserSafe.mockResolvedValue({ id: 1, email: 'a@example.test' })
    const before = [watchlistItem(2, 'MSFT')]
    api.getWatchlist.mockResolvedValue(before)
    const answer = deferred<WatchlistItem>()
    api.addToWatchlist.mockReturnValue(answer.promise)
    const page = renderWithClient(<CompanyPageClient initialCompany={company} initialFilings={filings} />)
    const star = await screen.findByRole('button', { name: 'Add to watchlist' })
    await waitFor(() => expect(api.getWatchlist).toHaveBeenCalledTimes(1))
    fireEvent.click(star)
    await waitFor(() => expect(api.addToWatchlist).toHaveBeenCalledWith('AAPL'))
    await waitFor(() => expect(page.client.getQueryData<WatchlistItem[]>(queryKeys.watchlist())).toHaveLength(2))
    api.getWatchlist.mockReturnValue(new Promise(() => {})) // the settle's refetch never answers, so the rollback shows
    await act(async () => answer.reject(new Error('Network Error')))
    await settle()
    expect(page.client.getQueryData(queryKeys.watchlist())).toEqual(before)
    expect(toast.error).toHaveBeenCalledWith("Couldn't update your watchlist. Please try again.")
    page.unmount()

    api.getNotificationPreferences.mockResolvedValue(preferences())
    const saved = deferred<NotificationPreferences>()
    api.updateNotificationPreferences.mockReturnValue(saved.promise)
    const form = renderWithClient(<NotificationPreferencesForm />)
    fireEvent.click(await screen.findByRole('switch', { name: 'Quarterly reports (10-Q)' }))
    await waitFor(() => expect(api.updateNotificationPreferences).toHaveBeenCalledTimes(1))
    const effective = preferences({ notify_10q: true, digest: 'weekly' })
    await act(async () => saved.resolve(effective))
    await settle()
    expect(form.client.getQueryData(queryKeys.notificationPreferences())).toEqual(effective)
  })
})
