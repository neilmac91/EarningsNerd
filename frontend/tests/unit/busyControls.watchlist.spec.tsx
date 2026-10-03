import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { WatchlistInsight, WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import { queryKeys } from '@/lib/queryKeys'
import PopularTickerChips from '@/features/watchlist/components/PopularTickerChips'
import WatchlistAddSearch from '@/features/watchlist/components/WatchlistAddSearch'
import YourCompanies from '@/features/dashboard/components/YourCompanies'
import CompanyPageClient from '@/app/company/[ticker]/page-client'
import FilingFeed from '@/features/dashboard/components/FilingFeed'

/**
 * Watchlist controls keep keyboard focus while their own add/remove/toggle is in flight, and the
 * company page's "Show full history" keeps it through a background refetch. They are aria-disabled
 * (+ aria-busy on the control whose request is in flight) with an early return, or the DS Button's
 * `loading`, never natively `disabled`: Chromium blurs a focused control that turns `disabled` to
 * <body>. jsdom does not blur disabled elements, so these specs pin the attributes, that focus is
 * never moved off the control, and that a second activation sends no second request. That includes
 * the gap after the request lands: an add or removal stays pending until the insights refetch that
 * recounts the ticker or drops its row, since the kept focus could otherwise send it again.
 *
 * Where a control's own success (or activation) unmounts it, focus is handed to a stable target
 * before it can fall to <body>: the search field after an add from the results, the "Your
 * companies" heading after a removal drops the row, the "SEC Filings" heading when "Show full
 * history" swaps the list, and the feed's "What's new" heading when an add replaces the onboarding
 * panel that held the chip or search. jsdom does move focus to <body> when the focused node is removed, so
 * those cases fail without the hand-off.
 */

const api = vi.hoisted(() => ({
  addToWatchlist: vi.fn(),
  removeFromWatchlist: vi.fn(),
  getWatchlist: vi.fn(),
  searchCompanies: vi.fn(),
  getCompany: vi.fn(),
  getCompanyFilings: vi.fn(),
  getSummary: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  getDashboardFeed: vi.fn(),
}))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({
  addToWatchlist: api.addToWatchlist,
  removeFromWatchlist: api.removeFromWatchlist,
  getWatchlist: api.getWatchlist,
}))
vi.mock('@/features/companies/api/companies-api', () => ({
  searchCompanies: api.searchCompanies,
  getCompany: api.getCompany,
}))
vi.mock('@/features/filings/api/filings-api', () => ({ getCompanyFilings: api.getCompanyFilings }))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getSummary: api.getSummary }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/features/dashboard/api/dashboard-api', () => ({ getDashboardFeed: api.getDashboardFeed }))
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

/** TanStack calls mutationFn a few microtasks after mutate(), so a request count is only
    meaningful once pending work has flushed — otherwise a second request would not be seen yet. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

/** Busy is announced (aria-busy + aria-disabled) and the control keeps focus. That a busy flag
    never turns it natively disabled is the rule-12 gate's job (busyControlsStayFocusable.spec.ts). */
function expectBusyAndFocused(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-busy', 'true')
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(document.activeElement).toBe(control)
}

/** A sibling sharing the pending flag: unavailable but focusable, and not the busy one. */
function expectUnavailableNotBusy(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(control).not.toHaveAttribute('aria-busy')
  expect(control).not.toBeDisabled()
}

/** Settled: available again and still the focused element. TanStack notifies observers on a
    later tick, so wait for the busy flag to clear before checking the rest. */
async function expectSettledAndFocused(control: HTMLElement) {
  await waitFor(() => expect(control).not.toHaveAttribute('aria-busy'))
  expect(control).not.toHaveAttribute('aria-disabled')
  expect(control).not.toBeDisabled()
  expect(document.activeElement).toBe(control)
}

const watchlistItem = (ticker: string): WatchlistItem => ({
  id: 7,
  company_id: 1,
  created_at: '2026-01-01T00:00:00Z',
  company: { id: 1, ticker, name: 'Apple Inc.' },
})

const insight = (id: number, ticker: string, name: string): WatchlistInsight => ({
  company: { id, ticker, name },
  latest_filing: null,
  total_filings: 0,
})

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

describe('PopularTickerChips', () => {
  // Rendered beside the dashboard's insights query but not inside the onboarding panel, so "after
  // it" means the chip row survives the add. Its only render site, FeedOnboarding, is replaced
  // wholesale by FilingFeed once the recount lands (watchlistCount > 0), taking the focused chip with
  // it; that hand-off is FilingFeed's ('FilingFeed onboarding' below).
  it('keeps focus on the chip through its add and the recount after it, and ignores repeat clicks on any chip', async () => {
    const post = deferred<WatchlistItem>()
    api.addToWatchlist.mockReturnValue(post.promise)
    const recount = deferred<WatchlistInsight[]>()
    const getInsights = vi
      .fn<() => Promise<WatchlistInsight[]>>()
      .mockResolvedValueOnce([])
      .mockReturnValueOnce(recount.promise)
    function DashboardInsights() {
      useQuery({ queryKey: queryKeys.watchlistInsights(), queryFn: getInsights })
      return null
    }
    renderWithClient(<><DashboardInsights /><PopularTickerChips /></>)
    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(1))

    const aapl = screen.getByRole('button', { name: 'Add AAPL to your watchlist' })
    const msft = screen.getByRole('button', { name: 'Add MSFT to your watchlist' })
    aapl.focus()
    fireEvent.click(aapl)
    await waitFor(() => expect(aapl).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(aapl)
    expectUnavailableNotBusy(msft)
    fireEvent.click(aapl)
    fireEvent.click(msft)
    await settle()
    expect(api.addToWatchlist).toHaveBeenCalledTimes(1)
    expect(api.addToWatchlist).toHaveBeenCalledWith('AAPL', expect.anything())

    // Added but not yet counted, so the panel would still be up: the chip stays busy and a second
    // activation posts nothing until the insights refetch lands.
    await act(async () => post.resolve(watchlistItem('AAPL')))
    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(2))
    await settle()
    expectBusyAndFocused(aapl)
    fireEvent.click(aapl)
    await settle()
    expect(api.addToWatchlist).toHaveBeenCalledTimes(1)

    await act(async () => recount.resolve([insight(1, 'AAPL', 'Apple Inc.')]))
    await expectSettledAndFocused(aapl)
    expect(msft).not.toHaveAttribute('aria-disabled')
  })
})

describe('WatchlistAddSearch result option', () => {
  it('keeps focus on the picked option through its add and a failed settle, and ignores repeat picks', async () => {
    api.searchCompanies.mockResolvedValue([
      { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.' },
      { id: 2, cik: '1751008', ticker: 'APP', name: 'AppLovin Corp' },
    ] satisfies Company[])
    const post = deferred<WatchlistItem>()
    api.addToWatchlist.mockReturnValue(post.promise)
    renderWithClient(<WatchlistAddSearch />)

    fireEvent.change(screen.getByLabelText('Search for a company to add to your watchlist'), {
      target: { value: 'app' },
    })
    const options = await screen.findAllByRole('option')
    const [apple, appLovin] = options
    apple.focus()
    fireEvent.click(apple)
    await waitFor(() => expect(apple).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(apple)
    expectUnavailableNotBusy(appLovin)
    fireEvent.click(apple)
    fireEvent.click(appLovin)
    await settle()
    expect(api.addToWatchlist).toHaveBeenCalledTimes(1)
    expect(api.addToWatchlist).toHaveBeenCalledWith('AAPL', expect.anything())

    // A failed add leaves the results open, so the picked option is still there — and still focused.
    await act(async () => post.reject(new Error('nope')))
    expect(await screen.findByText(/Couldn.t add that company/)).toBeInTheDocument()
    await expectSettledAndFocused(apple)
    expect(appLovin).not.toHaveAttribute('aria-disabled')
  })

  it('hands focus to the search field when a successful add closes the results under the picked option', async () => {
    api.searchCompanies.mockResolvedValue([
      { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.' },
    ] satisfies Company[])
    const post = deferred<WatchlistItem>()
    api.addToWatchlist.mockReturnValue(post.promise)
    renderWithClient(<WatchlistAddSearch />)

    const input = screen.getByLabelText('Search for a company to add to your watchlist')
    fireEvent.change(input, { target: { value: 'app' } })
    const apple = await screen.findByRole('option')
    apple.focus()
    fireEvent.click(apple)
    await waitFor(() => expect(apple).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(apple)

    await act(async () => post.resolve(watchlistItem('AAPL')))
    expect(await screen.findByText(/to your watchlist\./)).toBeInTheDocument()
    expect(apple).not.toBeInTheDocument()
    expect(document.activeElement).toBe(input)
    // Focusing the field (whose onFocus opens the results) must not reopen them over the new state.
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(input).toHaveValue('')
    expect(api.addToWatchlist).toHaveBeenCalledTimes(1)
  })
})

describe('YourCompanies remove button', () => {
  it('keeps focus through its removal request and a failed settle, and ignores repeat clicks on any row', async () => {
    const del = deferred<unknown>()
    api.removeFromWatchlist.mockReturnValue(del.promise)
    renderWithClient(
      <YourCompanies
        insights={[insight(1, 'AAPL', 'Apple Inc.'), insight(2, 'MSFT', 'Microsoft Corp')]}
        isLoading={false}
        isError={false}
        refetch={vi.fn()}
        isFetching={false}
      />,
    )

    const removeApple = screen.getByRole('button', { name: /Remove Apple.* from watchlist/ })
    const removeMicrosoft = screen.getByRole('button', { name: /Remove Microsoft.* from watchlist/ })
    removeApple.focus()
    fireEvent.click(removeApple)
    await waitFor(() => expect(removeApple).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(removeApple)
    expectUnavailableNotBusy(removeMicrosoft)
    fireEvent.click(removeApple)
    fireEvent.click(removeMicrosoft)
    await settle()
    expect(api.removeFromWatchlist).toHaveBeenCalledTimes(1)
    expect(api.removeFromWatchlist).toHaveBeenCalledWith('AAPL', expect.anything())

    // A failed removal keeps the row, and the keyboard user is still on its button.
    await act(async () => del.reject(new Error('nope')))
    await expectSettledAndFocused(removeApple)
    expect(removeMicrosoft).not.toHaveAttribute('aria-disabled')
  })

  it('stays busy until the refetch drops the focused row, then lands focus on the section heading', async () => {
    const del = deferred<unknown>()
    api.removeFromWatchlist.mockReturnValue(del.promise)
    const refetched = deferred<WatchlistInsight[]>()
    const getInsights = vi
      .fn<() => Promise<WatchlistInsight[]>>()
      .mockResolvedValueOnce([insight(1, 'AAPL', 'Apple Inc.'), insight(2, 'MSFT', 'Microsoft Corp')])
      .mockReturnValueOnce(refetched.promise)
    // The dashboard's own insights query: the removal's invalidation refetches it, and the row goes.
    function DashboardHost() {
      const { data, isLoading, isError, refetch, isFetching } = useQuery({
        queryKey: queryKeys.watchlistInsights(),
        queryFn: getInsights,
      })
      return (
        <YourCompanies
          insights={data}
          isLoading={isLoading}
          isError={isError}
          refetch={() => void refetch()}
          isFetching={isFetching}
        />
      )
    }
    renderWithClient(<DashboardHost />)

    const removeApple = await screen.findByRole('button', { name: /Remove Apple.* from watchlist/ })
    removeApple.focus()
    fireEvent.click(removeApple)
    await waitFor(() => expect(removeApple).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(removeApple)

    // Removed, but the row stays on screen until insights refetch: its button stays busy and focused,
    // and a second activation sends no second DELETE.
    await act(async () => del.resolve(undefined))
    await waitFor(() => expect(getInsights).toHaveBeenCalledTimes(2))
    await settle()
    expectBusyAndFocused(removeApple)
    fireEvent.click(removeApple)
    await settle()
    expect(api.removeFromWatchlist).toHaveBeenCalledTimes(1)

    await act(async () => refetched.resolve([insight(2, 'MSFT', 'Microsoft Corp')]))
    await waitFor(() => expect(removeApple).not.toBeInTheDocument())
    const heading = screen.getByRole('heading', { name: 'Your companies' })
    await waitFor(() => expect(document.activeElement).toBe(heading))
    expect(screen.getByRole('button', { name: /Remove Microsoft.* from watchlist/ })).toBeInTheDocument()
    expect(api.removeFromWatchlist).toHaveBeenCalledTimes(1)
  })
})

describe('Company page', () => {
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

  function renderCompanyPage() {
    api.getCompany.mockResolvedValue(company)
    api.getSummary.mockResolvedValue(null)
    api.getCurrentUserSafe.mockResolvedValue({ id: 1, email: 'a@example.test' })
    return renderWithClient(<CompanyPageClient initialCompany={company} initialFilings={filings} />)
  }

  it('keeps focus on the watchlist star through its toggle and after it, and ignores a repeat click', async () => {
    api.getCompanyFilings.mockResolvedValue(filings)
    api.getWatchlist.mockResolvedValueOnce([]).mockResolvedValue([watchlistItem('AAPL')])
    const post = deferred<WatchlistItem>()
    api.addToWatchlist.mockReturnValue(post.promise)
    renderCompanyPage()

    const star = await screen.findByRole('button', { name: 'Add to watchlist' })
    await waitFor(() => expect(api.getWatchlist).toHaveBeenCalledTimes(1))
    star.focus()
    fireEvent.click(star)
    await waitFor(() => expect(star).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(star)
    // The optimistic flip is on screen; a second press must not toggle it back mid-flight.
    expect(star).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(star)
    await settle()
    expect(api.addToWatchlist).toHaveBeenCalledTimes(1)
    expect(api.removeFromWatchlist).not.toHaveBeenCalled()

    await act(async () => post.resolve(watchlistItem('AAPL')))
    await waitFor(() => expect(api.getWatchlist).toHaveBeenCalledTimes(2))
    await expectSettledAndFocused(star)
    expect(star).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps focus on "Show full history" through a background refetch, and refuses a click while it runs', async () => {
    api.getWatchlist.mockResolvedValue([])
    api.getCompanyFilings.mockResolvedValueOnce(filings)
    const { client } = renderCompanyPage()

    const button = await screen.findByRole('button', { name: 'Show full history' })
    // Let the mount refetch of the server-seeded list finish, so the button starts out at rest.
    await waitFor(() => expect(button).not.toHaveAttribute('aria-busy'))
    const refetch = deferred<Filing[]>()
    api.getCompanyFilings.mockReturnValue(refetch.promise)
    button.focus()

    // A refetch the button did not start (e.g. on reconnect) begins while it holds focus.
    act(() => { void client.refetchQueries({ queryKey: queryKeys.companyFilings('AAPL') }) })
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(button)
    expect(button).toHaveTextContent('Loading full history…')
    fireEvent.click(button)
    await settle()
    expect(button).toBeInTheDocument()
    expect(api.getCompanyFilings).not.toHaveBeenCalledWith('AAPL', undefined, 300)

    await act(async () => refetch.resolve(filings))
    await waitFor(() => expect(button).toHaveTextContent('Show full history'))
    await expectSettledAndFocused(button)
  })

  it('hands focus to the "SEC Filings" heading when activating "Show full history" removes the button', async () => {
    api.getWatchlist.mockResolvedValue([])
    api.getCompanyFilings.mockResolvedValueOnce(filings)
    renderCompanyPage()

    const button = await screen.findByRole('button', { name: 'Show full history' })
    await waitFor(() => expect(button).not.toHaveAttribute('aria-busy'))
    const fullHistory = deferred<Filing[]>()
    api.getCompanyFilings.mockReturnValue(fullHistory.promise)
    button.focus()
    fireEvent.click(button)

    // The full-history key has no seed, so the list (and this button) gives way to the skeleton.
    await waitFor(() => expect(button).not.toBeInTheDocument())
    expect(screen.getByRole('status', { name: 'Loading filings' })).toBeInTheDocument()
    const heading = screen.getByRole('heading', { name: 'SEC Filings' })
    expect(document.activeElement).toBe(heading)
    await waitFor(() => expect(api.getCompanyFilings).toHaveBeenCalledWith('AAPL', undefined, 300))

    await act(async () => fullHistory.resolve(filings))
    await waitFor(() => expect(screen.queryByRole('status', { name: 'Loading filings' })).not.toBeInTheDocument())
    expect(document.activeElement).toBe(heading)
    expect(api.getCompanyFilings).toHaveBeenCalledTimes(2)
  })

  it('leaves focus alone when "Show full history" is activated without holding it (a mouse click)', async () => {
    api.getWatchlist.mockResolvedValue([])
    api.getCompanyFilings.mockResolvedValueOnce(filings)
    renderCompanyPage()

    const button = await screen.findByRole('button', { name: 'Show full history' })
    await waitFor(() => expect(button).not.toHaveAttribute('aria-busy'))
    api.getCompanyFilings.mockReturnValue(deferred<Filing[]>().promise)
    const elsewhere = screen.getByRole('heading', { name: 'SEC Filings' })
    expect(document.activeElement).not.toBe(button)
    fireEvent.click(button)

    await waitFor(() => expect(button).not.toBeInTheDocument())
    expect(document.activeElement).not.toBe(elsewhere)
  })
})

describe('FilingFeed onboarding', () => {
  // Its only render site for the chips and the onboarding search: an add that succeeds changes the
  // watchlist count, and the panel (with the focused chip) gives way to the feed's next state.
  function renderFeed(count: number) {
    const view = renderWithClient(<FilingFeed watchlistCount={count} />)
    const setCount = (next: number) =>
      view.rerender(<QueryClientProvider client={view.client}><FilingFeed watchlistCount={next} /></QueryClientProvider>)
    return { ...view, setCount }
  }

  it('hands focus to "What\'s new" when a successful add replaces the onboarding panel', async () => {
    api.getDashboardFeed.mockResolvedValue([])
    api.addToWatchlist.mockResolvedValue({})
    const { setCount } = renderFeed(0)

    const chip = (await screen.findAllByRole('button', { name: /^Add .+ to your watchlist$/ }))[0]
    chip.focus()
    fireEvent.click(chip)
    await waitFor(() => expect(api.addToWatchlist).toHaveBeenCalledTimes(1))
    // The dashboard passes the new count once its insights refetch lands.
    setCount(1)
    await waitFor(() => expect(chip.isConnected).toBe(false))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: "What's new" }))
  })

  it('leaves focus alone when the panel leaves while focus is elsewhere', async () => {
    api.getDashboardFeed.mockResolvedValue([])
    const { setCount } = renderFeed(0)
    await screen.findAllByRole('button', { name: /^Add .+ to your watchlist$/ })
    const elsewhere = document.createElement('button')
    document.body.appendChild(elsewhere)
    try {
      elsewhere.focus()
      setCount(1)
      await waitFor(() => expect(screen.queryByRole('button', { name: /^Add .+ to your watchlist$/ })).not.toBeInTheDocument())
      expect(document.activeElement).toBe(elsewhere)
    } finally {
      elsewhere.remove()
    }
  })
})
