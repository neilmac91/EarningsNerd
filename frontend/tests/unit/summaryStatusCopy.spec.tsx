import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { WatchlistInsight } from '@/features/watchlist/api/watchlist-api'
import WatchlistDashboardPage from '@/app/dashboard/watchlist/page'
import { summaryStatusBadge } from '@/features/watchlist/components/SummaryStatusBadge'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Watchlist insights tells the truth about each summary (audit DSW-02, DSW-03, DSW-14). The server's
 * `summary_status` prefix (backend/app/routers/watchlist.py) decides the card's next-step sentence and
 * its badge: `needs_regeneration` is true for missing, placeholder and error alike and false while a
 * summary is written, so read alone it called a summary in progress "current" and a missing one
 * "needs regenerating". A failed load shows its error card with a Retry and no empty card, since an
 * error is not an empty watchlist, and its Retry stays mounted, busy and focused while it refetches.
 */

const api = vi.hoisted(() => ({
  getCurrentUserSafe: vi.fn(),
  getWatchlistInsights: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
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

const USER: CurrentUser = {
  id: 1, email: 'a@example.test', full_name: 'Avery', is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}

const insight = (summary_status: string, needs_regeneration: boolean): WatchlistInsight => ({
  company: { id: 7, ticker: 'AAPL', name: 'Apple Inc.' },
  latest_filing: {
    id: 11, filing_type: '10-K', filing_date: '2025-10-31', period_end_date: '2025-09-27',
    summary_id: summary_status === 'ready' || summary_status === 'placeholder' ? 3 : null,
    summary_status, summary_created_at: null, summary_updated_at: null, needs_regeneration,
  },
  total_filings: 4,
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(queryKeys.currentUser(), USER)
  return render(<QueryClientProvider client={client}><WatchlistDashboardPage /></QueryClientProvider>)
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // clearAllMocks keeps queued once-values: a test that fails before its Retry click would leave its
  // never-resolving refetch for the next test to take, and one regression would read as two.
  api.getWatchlistInsights.mockReset()
})

// Each prefix with the needs_regeneration the server sends beside it.
const CASES: Array<{ status: string; needs: boolean; sentence: string; label: string; variant: string }> = [
  { status: 'ready', needs: false, sentence: 'Summary is current.', label: 'Ready', variant: 'beat' },
  { status: 'generating:summarizing', needs: false, sentence: 'A summary is being written.', label: 'Generating', variant: 'brand' },
  { status: 'missing', needs: true, sentence: 'No summary yet. Open the filing to generate one.', label: 'No summary yet', variant: 'neutral' },
  {
    status: 'placeholder', needs: true,
    sentence: "This summary isn't available right now. Open the filing and generate it again.", label: 'Unavailable', variant: 'warning',
  },
  { status: 'error', needs: true, sentence: 'The last attempt failed. Open the filing and generate it again.', label: 'Error', variant: 'miss' },
]

describe('the watchlist card states each summary status', () => {
  it.each(CASES)('$status: its own sentence and badge', async ({ status, needs, sentence, label }) => {
    api.getWatchlistInsights.mockResolvedValue([insight(status, needs)])
    renderPage()

    const card = (await screen.findByRole('heading', { level: 2, name: 'Apple Inc.' })).closest('div.p-6') as HTMLElement
    expect(within(card).getByText(sentence)).toBeInTheDocument()
    expect(within(card).getByText(label)).toBeInTheDocument()
    // Every other status's sentence is absent: the prefix decides, one sentence per card.
    for (const other of CASES.filter((c) => c.sentence !== sentence)) {
      expect(within(card).queryByText(other.sentence)).toBeNull()
    }
  })

  it.each(CASES)('$status: the badge variant comes from the prefix, whatever needs_regeneration says', ({ status, needs, label, variant }) => {
    expect(summaryStatusBadge(status, needs)).toEqual({ label, variant })
    expect(summaryStatusBadge(status, !needs)).toEqual({ label, variant })
  })

  // The stage after `generating:` is the pipeline's key; the chip never prints it (the filing page's
  // step log speaks in phrases, not keys), so every stage the server can send reads the same word.
  it.each(['generating', 'generating:initializing', 'generating:queued', 'generating:fetching', 'generating:parsing',
    'generating:analyzing', 'generating:summarizing', 'generating:completed', 'generating:partial'])(
    '%s: the chip reads "Generating" and names no stage key',
    (status) => {
      expect(summaryStatusBadge(status, false)).toEqual({ label: 'Generating', variant: 'brand' })
    },
  )

  it('an unknown prefix falls back on needs_regeneration, in sentence case', () => {
    expect(summaryStatusBadge('queued', true)).toEqual({ label: 'Needs regenerating', variant: 'warning' })
    expect(summaryStatusBadge('queued', false)).toEqual({ label: 'Pending', variant: 'neutral' })
  })
})

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}

/** TanStack starts a fetch and notifies observers a few ticks after the call, so a busy flag is only
    meaningful once pending work has flushed. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

describe('a failed load', () => {
  it('shows the error card with a Retry and no empty card; the Retry stays up, busy and focused through its refetch', async () => {
    const refetched = deferred<WatchlistInsight[]>()
    api.getWatchlistInsights.mockRejectedValueOnce(new Error('Network down')).mockReturnValueOnce(refetched.promise)
    renderPage()

    const heading = await screen.findByRole('heading', { level: 2, name: "Couldn't load your watchlist" })
    const card = heading.closest('[role="alert"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(within(card).getByText('Try again in a moment.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'No watchlist companies yet' })).toBeNull()

    const retry = within(card).getByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    await waitFor(() => expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2))
    await settle()
    // In flight: the error card and its Retry stay mounted (the query itself is back to pending, so a
    // card on the raw isError would have gone), the Retry busy and still the focused element.
    expect(card.isConnected).toBe(true)
    expect(retry.isConnected).toBe(true)
    expect(retry).toHaveAttribute('aria-busy', 'true')
    expect(document.activeElement).toBe(retry)
    expect(screen.queryByRole('heading', { name: 'No watchlist companies yet' })).toBeNull()

    await act(async () => refetched.resolve([]))
    expect(await screen.findByRole('heading', { level: 2, name: 'No watchlist companies yet' })).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('heading', { name: "Couldn't load your watchlist" })).toBeNull())
    expect(api.getWatchlistInsights).toHaveBeenCalledTimes(2)
  })

  it('an empty list says so, and names what an alert is', async () => {
    api.getWatchlistInsights.mockResolvedValue([])
    renderPage()

    expect(await screen.findByRole('heading', { level: 2, name: 'No watchlist companies yet' })).toBeInTheDocument()
    expect(
      screen.getByText('Use the search above to follow your first company. When it files a form you chose in Filing alerts, we email you and list it under Notifications.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: "Couldn't load your watchlist" })).toBeNull()
  })
})
