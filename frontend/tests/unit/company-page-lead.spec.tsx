import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import CompanyPageClient from '@/app/company/[ticker]/page-client'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The company page's lead and aside (2026-10 critique, 1b): the company stated in the filing page's
 * identity vocabulary, its latest filing, ONE primary action that opens that filing, and the Compare
 * periods card beside the filings when the list holds two annual periods to compare.
 */

const api = vi.hoisted(() => ({
  getWatchlist: vi.fn(),
  getCompany: vi.fn(),
  getCompanyFilings: vi.fn(),
  getSummary: vi.fn(),
  getWhatChanged: vi.fn(),
  getCurrentUserSafe: vi.fn(),
}))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({
  addToWatchlist: vi.fn(),
  removeFromWatchlist: vi.fn(),
  getWatchlist: api.getWatchlist,
}))
vi.mock('@/features/companies/api/companies-api', () => ({ getCompany: api.getCompany }))
vi.mock('@/features/filings/api/filings-api', () => ({ getCompanyFilings: api.getCompanyFilings }))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getSummary: api.getSummary, getWhatChanged: api.getWhatChanged }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
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

// A case about the summary read's result lets the read land before it asserts: the lead says "Open
// latest filing" while the read is pending too, so an assertion made before then proves nothing.
async function settleSummaryRead() {
  await waitFor(() => expect(api.getSummary).toHaveBeenCalledWith(12))
  await act(async () => {
    await api.getSummary.mock.results[0].value
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

const COMPANY: Company = { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' }
const filing = (id: number, filing_type: string, filed: string, report: string): Filing => ({
  id,
  filing_type,
  filing_date: `${filed}T00:00:00+00:00`,
  report_date: `${report}T00:00:00+00:00`,
  accession_number: `0000320193-${id}`,
  document_url: `https://www.sec.gov/doc/${id}`,
  sec_url: `https://www.sec.gov/edgar/${id}`,
})
const QUARTER = filing(12, '10-Q', '2026-01-30', '2025-12-27')
const ANNUAL = filing(11, '10-K', '2025-10-31', '2025-09-27')
const PRIOR_ANNUAL = filing(10, '10-K', '2024-11-01', '2024-09-28')
const REPORT: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Year over year',
  prior_filing: { filing_id: 10, filing_type: '10-K', filing_date: '2024-11-01T00:00:00+00:00', period_end_date: '2024-09-28T00:00:00+00:00' },
  metrics: {
    headline: 'Revenue rose 6.4%.',
    items: [{ metric: 'revenue', label: 'Revenue', direction: 'up', pct: 6.4, current: 416e9, prior: 391e9, display: '+6.4%', tone: 'gain' }],
    data_quality: 'ok',
  },
  risks: null,
  key_changes: null,
  has_changes: true,
}

function renderPage(filings: Filing[], { signedIn = false } = {}) {
  api.getCompany.mockResolvedValue(COMPANY)
  api.getCompanyFilings.mockResolvedValue(filings)
  api.getCurrentUserSafe.mockResolvedValue(signedIn ? { id: 1, email: 'a@example.test' } : null)
  api.getWatchlist.mockResolvedValue([])
  api.getWhatChanged.mockResolvedValue(REPORT)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <CompanyPageClient initialCompany={COMPANY} initialFilings={filings} />
    </QueryClientProvider>,
  )
}

/** The primary-colorway actions on the page (buttonVariants primary: a bg-brand fill). A pressed
 *  segment of the form filter wears the same colorway as a state, not an action, so it is left out. */
const primaryActions = (container: HTMLElement) =>
  Array.from(container.querySelectorAll<HTMLElement>('a, button:not([aria-pressed])')).filter((el) =>
    /(^|\s)bg-brand(\s|$)/.test(el.className),
  )

afterEach(() => vi.clearAllMocks())

describe('Company page lead', () => {
  it('states the company and its latest filing, and opens that filing as its one primary action', async () => {
    api.getSummary.mockResolvedValue(null)
    const { container } = renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
    expect(within(header).getByText(/^Latest filing/).closest('p')).toHaveTextContent(/Latest filing 10-Q\s*·\s*,\s*quarter ended Dec 27, 2025/)
    const open = await within(header).findByRole('link', { name: 'Summarize latest filing' })
    expect(open).toHaveAttribute('href', '/filing/12')
    expect(api.getSummary).toHaveBeenCalledWith(12)
    expect(primaryActions(container)).toEqual([open])
    // The old "← Back" link and the in-list lead are gone; the breadcrumb leads home.
    expect(screen.queryByText('← Back')).toBeNull()
    expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
  })

  it('says "summary ready" and opens the summary once the latest filing has one', async () => {
    api.getSummary.mockResolvedValue({ id: 5, filing_id: 12, business_overview: 'Apple designs devices.' })
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const header = screen.getByRole('banner')
    expect(await within(header).findByRole('link', { name: 'Open latest summary' })).toHaveAttribute('href', '/filing/12')
    expect(within(header).getByText('summary ready')).toBeInTheDocument()
  })

  // "Summarize" promises a run, so it waits for the summary read to say there is none (null). Until then,
  // or when the read fails, the lead opens the filing, which never flashes ahead of "Open latest summary".
  it('opens the filing while the summary read is pending, then says what it found', async () => {
    let answer: (value: unknown) => void = () => {}
    api.getSummary.mockReturnValue(new Promise((resolve) => { answer = resolve }))
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const header = screen.getByRole('banner')
    await waitFor(() => expect(api.getSummary).toHaveBeenCalledWith(12))
    expect(within(header).getByRole('link', { name: 'Open latest filing' })).toHaveAttribute('href', '/filing/12')
    expect(within(header).queryByRole('link', { name: /Summarize|Open latest summary/ })).toBeNull()
    answer({ id: 5, filing_id: 12, business_overview: 'Apple designs devices.' })
    expect(await within(header).findByRole('link', { name: 'Open latest summary' })).toHaveAttribute('href', '/filing/12')
  })

  it('opens the filing when the summary read fails', async () => {
    api.getSummary.mockRejectedValue(new Error('offline'))
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const header = screen.getByRole('banner')
    await waitFor(() => expect(api.getSummary).toHaveBeenCalledWith(12))
    expect(await within(header).findByRole('link', { name: 'Open latest filing' })).toHaveAttribute('href', '/filing/12')
    expect(within(header).queryByRole('link', { name: /Summarize|Open latest summary/ })).toBeNull()
  })

  // A row the filing page will not show as a summary is not one, and the lead promises no run over it:
  // it opens the filing, where the page shows its state (its Retry replaces the row for any signed-in
  // user, decision A of tasks/decisions-2026-10-09-design-followups.md).
  it.each([
    ['a placeholder', { business_overview: 'Generating summary...' }],
    ['a writer error', { business_overview: 'Apple designs devices.', raw_summary: { writer_error: 'timeout' } }],
    ['the fallback body', { business_overview: 'Summary temporarily unavailable. Please retry.' }],
    ['the API-key placeholder', { business_overview: 'Summary generation requires OpenAI API key. Please configure OPENAI_API_KEY in your .env file.' }],
  ])('says nothing is ready while the stored summary is %s, and only opens the filing', async (_, stored) => {
    api.getSummary.mockResolvedValue({ id: 5, filing_id: 12, ...stored })
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const header = screen.getByRole('banner')
    // The lead also says "Open latest filing" while the read is pending, so the read must land first.
    await settleSummaryRead()
    expect(within(header).getByRole('link', { name: 'Open latest filing' })).toHaveAttribute('href', '/filing/12')
    expect(within(header).queryByText('summary ready')).toBeNull()
    expect(within(header).queryByRole('link', { name: /Summarize|Open latest summary/ })).toBeNull()
  })

  it('keeps the watchlist a secondary action with a visible label for a signed-in visitor', async () => {
    api.getSummary.mockResolvedValue(null)
    const { container } = renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL], { signedIn: true })
    const star = await screen.findByRole('button', { name: 'Add to watchlist' })
    expect(star).toHaveAttribute('aria-pressed', 'false')
    expect(star).not.toHaveAttribute('aria-label')
    expect(star.className).not.toMatch(/(^|\s)bg-brand(\s|$)/)
    expect(primaryActions(container)).toEqual([await screen.findByRole('link', { name: 'Summarize latest filing' })])
  })

  it("sets the watched star in the button's own ink, never a status colour (CO-07)", async () => {
    api.getSummary.mockResolvedValue(null)
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL], { signedIn: true })
    api.getWatchlist.mockResolvedValue([{ id: 1, company_id: 1, created_at: '2026-01-01T00:00:00Z', company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' } }])
    const star = await screen.findByRole('button', { name: 'Remove from watchlist' })
    expect(star).toHaveAttribute('aria-pressed', 'true')
    expect(star.querySelector('svg')?.getAttribute('class') ?? '').not.toMatch(/warning/)
  })

  it('puts the Compare periods card beside the filings for the newest annual report', async () => {
    api.getSummary.mockResolvedValue(null)
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const card = screen.getByRole('complementary', { name: 'Compare periods' })
    expect(await within(card).findByRole('link', { name: 'Open change report' })).toHaveAttribute('href', '/filing/11#what-changed')
    expect(api.getWhatChanged).toHaveBeenCalledWith(11)
    // The aside and the filings share one grid: two tracks from lg up, one below.
    const grid = card.parentElement as HTMLElement
    expect(grid.className).toMatch(/grid-cols-1/)
    expect(grid.className).toMatch(/lg:grid-cols-\[minmax\(0,1fr\)_20rem\]/)
    expect(within(grid).getByRole('region', { name: 'SEC filings' })).toBeInTheDocument()
  })

  it('leaves the card out, and the list full width, without an earlier annual period to compare', async () => {
    api.getSummary.mockResolvedValue(null)
    renderPage([QUARTER, ANNUAL])
    await waitFor(() => expect(api.getSummary).toHaveBeenCalled())
    expect(screen.queryByRole('complementary', { name: 'Compare periods' })).toBeNull()
    expect(api.getWhatChanged).not.toHaveBeenCalled()
    const list = screen.getByRole('region', { name: 'SEC filings' })
    expect((list.parentElement as HTMLElement).className).not.toMatch(/lg:grid-cols-/)
  })
})

describe('Company page when the company does not load (CO-05)', () => {
  function renderUnseeded() {
    api.getCompanyFilings.mockResolvedValue([QUARTER, ANNUAL, PRIOR_ANNUAL])
    api.getCurrentUserSafe.mockResolvedValue(null)
    api.getSummary.mockResolvedValue(null)
    api.getWhatChanged.mockResolvedValue(REPORT)
    // The company query's own `retry: 1` still runs; the client's retryDelay of 0 only drops TanStack's 1s wait before it.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })
    return {
      client,
      ...render(
        <QueryClientProvider client={client}>
          <CompanyPageClient />
        </QueryClientProvider>,
      ),
    }
  }

  const deferred = <T,>() => {
    let resolve!: (value: T) => void
    let reject!: (reason: unknown) => void
    const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
    return { promise, resolve, reject }
  }

  /** TanStack notifies its observers on a later task: let that render land before asserting it changed nothing. */
  const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

  /** A 503 load failure, then a Retry pressed from the keyboard's focus whose answer the test holds. */
  async function pressRetryOverFailure() {
    api.getCompany.mockRejectedValue(new ApiError(503, 'Service unavailable'))
    renderUnseeded()
    const card = (await screen.findByRole('heading', { name: 'Couldn’t load this company' })).closest('[role="alert"]') as HTMLElement
    const retry = within(card).getByRole('button', { name: 'Retry' })
    const answer = deferred<Company>()
    api.getCompany.mockReturnValueOnce(answer.promise)
    retry.focus()
    fireEvent.click(retry)
    // The query has no data, so its refetch goes back to pending: the card stays, not the page spinner,
    // with the pressed Retry still mounted, busy and focused.
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    expect(retry.isConnected).toBe(true)
    expect(document.activeElement).toBe(retry)
    expect(screen.getByRole('heading', { name: 'Couldn’t load this company' })).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading company' })).toBeNull()
    return { retry, answer }
  }

  it('says it could not load the company, never prints the raw error, and a Retry loads the page', async () => {
    api.getCompany.mockRejectedValue(new ApiError(503, 'Upstream EDGAR proxy timed out at 10.0.0.4'))
    renderUnseeded()
    const title = await screen.findByRole('heading', { name: 'Couldn’t load this company' }, { timeout: 4000 })
    const card = title.closest('[role="alert"]') as HTMLElement
    expect(card).toHaveTextContent('Try again in a moment.')
    expect(card).not.toHaveTextContent(/EDGAR proxy|10\.0\.0\.4|Error:/)
    expect(screen.queryByText('Company not found')).toBeNull()

    api.getCompany.mockResolvedValue(COMPANY)
    act(() => screen.getByRole('button', { name: 'Retry' }).click())
    expect(await screen.findByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
  })

  it('reads a 404 as not found, with the scope of the search and no Retry', async () => {
    api.getCompany.mockRejectedValue(new ApiError(404, 'Company not found'))
    renderUnseeded()
    expect(await screen.findByRole('heading', { name: 'Company not found' }, { timeout: 4000 })).toBeInTheDocument()
    expect(screen.getByText('No company with a ticker on SEC EDGAR matches "AAPL".')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Go back home' })).toHaveAttribute('href', '/')
  })

  it('keeps the card and its focused Retry busy through the retry, then hands focus to the "SEC filings" heading', async () => {
    const { retry, answer } = await pressRetryOverFailure()
    await act(async () => answer.resolve(COMPANY))
    expect(await screen.findByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
    expect(retry.isConnected).toBe(false)
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'SEC filings' })))
  })

  it('hands focus to the not-found title when the retry answers 404', async () => {
    const { retry, answer } = await pressRetryOverFailure()
    // The query's one retry asks again, and hears the same answer.
    api.getCompany.mockRejectedValue(new ApiError(404, 'Company not found'))
    await act(async () => answer.reject(new ApiError(404, 'Company not found')))
    const title = await screen.findByRole('heading', { name: 'Company not found' })
    expect(retry.isConnected).toBe(false)
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull()
    await waitFor(() => expect(document.activeElement).toBe(title))
  })

  it('hands focus to the coverage card title when the retry answers with an unsupported foreign issuer', async () => {
    const { retry, answer } = await pressRetryOverFailure()
    await act(async () => answer.resolve({ ...COMPANY, coverage_status: 'unsupported_foreign', coverage_reason: 'No SEC financial reports.' }))
    const title = await screen.findByRole('heading', { name: 'Apple Inc.' })
    expect(retry.isConnected).toBe(false)
    await waitFor(() => expect(document.activeElement).toBe(title))
  })

  it('keeps a 404 not found through a background refetch: no Retry appears, and the focused link stays', async () => {
    api.getCompany.mockRejectedValue(new ApiError(404, 'Company not found'))
    const { client } = renderUnseeded()
    const home = await screen.findByRole('link', { name: 'Go back home' })
    home.focus()
    const answer = deferred<Company>()
    api.getCompany.mockReturnValue(answer.promise)
    // A reconnect or an invalidation refetches it: the errored query has no data, so it goes back to
    // pending, its own error cleared, while the fetch runs.
    act(() => { void client.refetchQueries({ queryKey: queryKeys.company('AAPL') }) })
    await waitFor(() => expect(client.getQueryState(queryKeys.company('AAPL'))?.status).toBe('pending'))
    await settle()
    expect(screen.getByRole('heading', { name: 'Company not found' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Couldn’t load this company' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Go back home' })).toBe(home)
    expect(document.activeElement).toBe(home)

    await act(async () => answer.reject(new ApiError(404, 'Company not found')))
    await waitFor(() => expect(client.getQueryState(queryKeys.company('AAPL'))?.status).toBe('error'))
    await settle()
    expect(screen.getByRole('heading', { name: 'Company not found' })).toBeInTheDocument()
    expect(document.activeElement).toBe(home)
  })
})
