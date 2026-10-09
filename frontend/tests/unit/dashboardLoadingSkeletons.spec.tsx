import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { WatchlistInsight } from '@/features/watchlist/api/watchlist-api'
import SettingsPage from '@/app/dashboard/settings/page'
import WatchlistDashboardPage from '@/app/dashboard/watchlist/page'
import { queryKeys } from '@/lib/queryKeys'

/**
 * P-09 (Design Critique 2026-10): the account settings and watchlist pages never swap themselves for a
 * full-page spinner. While they load they render their own header over bones in the loaded layout's
 * cards; the content replaces the bones and crossfades in (hooks/useContentIn), the header staying the
 * same node; a page whose data is cached paints its content at once, without the entrance.
 */

const api = vi.hoisted(() => ({
  getCurrentUserSafe: vi.fn(),
  getConnections: vi.fn(),
  getSubscriptionStatus: vi.fn(),
  getUsage: vi.fn(),
  getNotificationPreferences: vi.fn(),
  getWatchlistInsights: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: api.getCurrentUserSafe,
  getConnections: api.getConnections,
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
  unlinkProvider: vi.fn(),
  logoutAllSessions: vi.fn(),
  exportUserData: vi.fn(),
  deleteUserAccount: vi.fn(),
}))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: api.getSubscriptionStatus,
  getUsage: api.getUsage,
  createPortalSession: vi.fn(),
}))
vi.mock('@/features/notifications/api/notifications-api', () => ({
  getNotificationPreferences: api.getNotificationPreferences,
  updateNotificationPreferences: vi.fn(),
}))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({
  getWatchlistInsights: api.getWatchlistInsights,
  addToWatchlist: vi.fn(),
}))
vi.mock('@/features/companies/api/companies-api', () => ({ searchCompanies: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}

const USER: CurrentUser = {
  id: 1, email: 'a@example.test', full_name: 'Avery', is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}
const INSIGHTS: WatchlistInsight[] = [
  { company: { id: 7, ticker: 'AAPL', name: 'Apple Inc.' }, latest_filing: null, total_filings: 3 },
]

function renderPage(page: ReactNode, seed?: (client: QueryClient) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seed?.(client)
  return render(<QueryClientProvider client={client}>{page}</QueryClientProvider>)
}

/** What a loading page must never show: a spinner standing in for the page. */
const spinner = (container: HTMLElement) => container.querySelector('.animate-spin')

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('account settings while the account loads', () => {
  it('shows its own header over bones in the sections’ cards, never a spinner', () => {
    api.getCurrentUserSafe.mockReturnValue(new Promise(() => {}))
    const { container } = renderPage(<SettingsPage />)

    expect(screen.getByRole('heading', { level: 1, name: 'Account settings' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading your settings' })).toHaveTextContent('Loading your settings…')
    expect(spinner(container)).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Profile' })).toBeNull()
  })

  it('replaces the bones with the sections, which crossfade in under the same header', async () => {
    const me = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockReturnValue(me.promise)
    api.getConnections.mockReturnValue(new Promise(() => {}))
    api.getSubscriptionStatus.mockReturnValue(new Promise(() => {}))
    api.getUsage.mockReturnValue(new Promise(() => {}))
    api.getNotificationPreferences.mockReturnValue(new Promise(() => {}))
    renderPage(<SettingsPage />)
    const title = screen.getByRole('heading', { level: 1 })

    await act(async () => me.resolve(USER))

    const profile = await screen.findByRole('heading', { name: 'Profile' })
    expect(profile.closest('.animate-content-in')).not.toBeNull()
    expect(profile.closest('.animate-content-in')).toHaveClass('motion-reduce:animate-none')
    expect(screen.getByRole('heading', { level: 1 })).toBe(title)
  })

  it('paints the sections at once, without the entrance, when the account is cached', () => {
    api.getConnections.mockReturnValue(new Promise(() => {}))
    api.getSubscriptionStatus.mockReturnValue(new Promise(() => {}))
    api.getUsage.mockReturnValue(new Promise(() => {}))
    api.getNotificationPreferences.mockReturnValue(new Promise(() => {}))
    const { container } = renderPage(<SettingsPage />, (client) => client.setQueryData(queryKeys.currentUser(), USER))

    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()
    expect(container.querySelector('.animate-content-in')).toBeNull()
  })
})

describe('watchlist insights while the account or the list loads', () => {
  it('shows its own header and live add field over the cards’ bones, never a spinner', () => {
    api.getCurrentUserSafe.mockReturnValue(new Promise(() => {}))
    const { container } = renderPage(<WatchlistDashboardPage />)

    expect(screen.getByRole('heading', { level: 1, name: 'Watchlist insights' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Search for a company to add to your watchlist' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading your watchlist' })).toHaveTextContent('Loading your watchlist…')
    expect(spinner(container)).toBeNull()
  })

  it('keeps the bones until the list arrives, then the list crossfades in under the same header', async () => {
    const insights = deferred<WatchlistInsight[]>()
    api.getCurrentUserSafe.mockResolvedValue(USER)
    api.getWatchlistInsights.mockReturnValue(insights.promise)
    renderPage(<WatchlistDashboardPage />)
    const title = screen.getByRole('heading', { level: 1 })
    const field = screen.getByRole('textbox', { name: 'Search for a company to add to your watchlist' })
    fireEvent.change(field, { target: { value: 'Micro' } })

    // The account answered; the list is still on its way: still bones.
    await waitFor(() => expect(api.getWatchlistInsights).toHaveBeenCalled())
    expect(screen.getByRole('status', { name: 'Loading your watchlist' })).toBeInTheDocument()

    await act(async () => insights.resolve(INSIGHTS))

    const company = await screen.findByRole('heading', { name: 'Apple Inc.' })
    const list = company.closest('.grid')
    expect(list).toHaveClass('animate-content-in', 'motion-reduce:animate-none')
    expect(screen.queryByRole('status', { name: 'Loading your watchlist' })).toBeNull()
    // The header and the add field are the same nodes: what was typed while the list loaded stays, and
    // neither fades in again.
    expect(screen.getByRole('heading', { level: 1 })).toBe(title)
    expect(screen.getByRole('textbox', { name: 'Search for a company to add to your watchlist' })).toBe(field)
    expect(field).toHaveValue('Micro')
    expect(field.closest('.animate-content-in')).toBeNull()
  })

  it('paints the list at once, without the entrance, when the account and the list are cached', () => {
    const { container } = renderPage(<WatchlistDashboardPage />, (client) => {
      client.setQueryData(queryKeys.currentUser(), USER)
      client.setQueryData(queryKeys.watchlistInsights(), INSIGHTS)
    })

    expect(screen.getByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument()
    expect(container.querySelector('.animate-content-in')).toBeNull()
  })
})
