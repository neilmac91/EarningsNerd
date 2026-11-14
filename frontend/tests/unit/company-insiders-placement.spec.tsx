import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import CompanyPageClient from '@/app/company/[ticker]/page-client'
import InsidersPageClient from '@/app/company/[ticker]/insiders/page-client'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Where insider activity lives (founder direction, 2026-11-14): the company page's filings keep the page, and insider
 * activity is a card in the side column that links to a page of its own, /company/{ticker}/insiders.
 *
 *   - The company page: no insider section above the filings; the card in the side column, after Compare periods, for
 *     a beta account on a company that is no foreign private issuer, and for nobody else.
 *   - The insider page: the company in the lead with the way back to its filings; the full panel for a beta account;
 *     for any other reader a card that says it is in beta, and no request to the insider endpoint.
 */

const api = vi.hoisted(() => ({
  getWatchlist: vi.fn(),
  getCompany: vi.fn(),
  getCompanyFilings: vi.fn(),
  getSummary: vi.fn(),
  getWhatChanged: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  getInsiderActivity: vi.fn(),
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
vi.mock('@/features/insiders/api/insiders-api', () => ({ getInsiderActivity: api.getInsiderActivity }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_FINANCIAL_CHARTS: false,
  ENABLE_INSIDER_ACTIVITY: true,
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
const FOREIGN_ANNUAL = filing(20, '20-F', '2026-03-01', '2025-12-31')

const reader = (over: Record<string, unknown> = {}) => ({
  id: 1, email: 'reader@example.test', full_name: null, is_pro: false, is_beta: true, is_admin: false, email_verified: true, ...over,
})
const NOT_BETA = reader({ is_beta: false })

const ACTIVITY = {
  ticker: 'AAPL', company_name: 'Apple Inc.', cik: '320193', window_days: 90,
  summary: {
    window_days: 90, buy_count: 0, sell_count: 3, buy_shares: 0, sell_shares: 9500, buy_value: null, sell_value: 1461500,
    net_shares: -9500, net_value: -1461500, discretionary_net_shares: -9500, plan_10b5_1_sell_shares: 0, last_transaction_date: '2026-10-01',
  },
  transactions: [{
    insider_name: 'Jane Doe', insider_title: 'Chief Financial Officer', is_director: false, is_officer: true, is_ten_pct_owner: false,
    ticker: 'AAPL', transaction_date: '2026-10-01', transaction_code: 'S', transaction_label: 'Open-market sale', shares: 9500,
    price: 153.84, value: 1461500, acquired_disposed: 'D', is_10b5_1: false, accession: '0000320193-26-000011', filed_date: '2026-10-03',
  }],
  total_transactions: 3,
  scan: { status: 'complete', filings_listed: 60, filings_read: 60, oldest_filed_date: '2025-11-20', refreshed_at: '2026-11-14T12:00:00Z', retry_after_seconds: null },
}

function mount(page: ReactNode, filings: Filing[], user: unknown) {
  api.getCompany.mockResolvedValue(COMPANY)
  api.getCompanyFilings.mockResolvedValue(filings)
  api.getCurrentUserSafe.mockResolvedValue(user)
  api.getWatchlist.mockResolvedValue([])
  api.getSummary.mockResolvedValue(null)
  api.getWhatChanged.mockResolvedValue({ has_prior: false, has_changes: false })
  api.getInsiderActivity.mockResolvedValue(ACTIVITY)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{page}</QueryClientProvider>)
}
const companyPage = (filings: Filing[], user: unknown = reader()) =>
  mount(<CompanyPageClient initialCompany={COMPANY} initialFilings={filings} />, filings, user)
const insidersPage = (filings: Filing[], user: unknown = reader()) =>
  mount(<InsidersPageClient initialCompany={COMPANY} initialFilings={filings} />, filings, user)

/** Let the reader's read and anything it enables settle. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 20))

beforeEach(() => Object.values(api).forEach((fn) => fn.mockReset()))
afterEach(cleanup)

describe('the company page: insider activity is a card in the side column', () => {
  it('puts the card after Compare periods, in the column beside the filings, linking to the insider page', async () => {
    companyPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const card = await screen.findByRole('complementary', { name: 'Insider activity' })
    expect(await within(card).findByRole('link', { name: 'Open insider activity' })).toHaveAttribute('href', '/company/AAPL/insiders')

    const column = card.parentElement as HTMLElement
    const asides = within(column).getAllByRole('complementary').map((el) => el.getAttribute('aria-labelledby') && within(el).getByRole('heading').textContent)
    expect(asides).toEqual(['Compare periods', 'Insider activity'])
    const grid = column.parentElement as HTMLElement
    expect(grid.className).toMatch(/grid-cols-1/)
    expect(grid.className).toMatch(/\[@media\(min-width:64rem\)\]:grid-cols-\[minmax\(0,1fr\)_20rem\]/)
    // The filings come first in the grid, so on a phone the card follows them.
    expect(grid.firstElementChild).toBe(screen.getByRole('region', { name: 'SEC filings' }))
  })

  it('draws no insider section above the filings: the filings are the first thing in the page’s main region', async () => {
    companyPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    await screen.findByRole('complementary', { name: 'Insider activity' })
    const main = screen.getByRole('main')
    expect(within(main).queryByRole('group', { name: 'Time window' })).toBeNull()   // the full panel's control
    expect(within(main).queryByRole('table')).toBeNull()                            // and its trades table
    expect(main.firstElementChild?.firstElementChild).toBe(screen.getByRole('region', { name: 'SEC filings' }))
  })

  it('opens the side column for the card alone when there is no pair of annual periods to compare', async () => {
    companyPage([QUARTER, ANNUAL])
    const card = await screen.findByRole('complementary', { name: 'Insider activity' })
    expect(screen.queryByRole('complementary', { name: 'Compare periods' })).toBeNull()
    expect((card.parentElement!.parentElement as HTMLElement).className).toMatch(/grid-cols-\[minmax\(0,1fr\)_20rem\]/)
  })

  it.each([
    ['a guest', null],
    ['an account that is not a beta tester', NOT_BETA],
  ])('%s gets no card, no column for it and no request', async (_, user) => {
    companyPage([QUARTER, ANNUAL], user)
    await waitFor(() => expect(api.getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(screen.queryByRole('complementary', { name: 'Insider activity' })).toBeNull()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()
    const list = screen.getByRole('region', { name: 'SEC filings' })
    expect((list.parentElement as HTMLElement).className).not.toMatch(/grid-cols-\[minmax/)
  })

  it.each([401, 403, 404])('a %i from the endpoint (its switch off, or a company it does not know) leaves no card and no column', async (status) => {
    companyPage([QUARTER, ANNUAL])
    api.getInsiderActivity.mockRejectedValue(new ApiError(status, 'Refused'))
    await waitFor(() => expect(api.getInsiderActivity).toHaveBeenCalled())
    await settle()
    expect(screen.queryByRole('complementary', { name: 'Insider activity' })).toBeNull()
    const list = screen.getByRole('region', { name: 'SEC filings' })
    expect((list.parentElement as HTMLElement).className).not.toMatch(/grid-cols-\[minmax/)
    expect(api.getInsiderActivity).toHaveBeenCalledTimes(1)
  })

  it('shows no card, and opens no column, until the endpoint first answers', async () => {
    companyPage([QUARTER, ANNUAL])
    api.getInsiderActivity.mockReturnValue(new Promise(() => {}))
    await waitFor(() => expect(api.getInsiderActivity).toHaveBeenCalled())
    await settle()
    expect(screen.queryByRole('complementary', { name: 'Insider activity' })).toBeNull()
    const list = screen.getByRole('region', { name: 'SEC filings' })
    expect((list.parentElement as HTMLElement).className).not.toMatch(/grid-cols-\[minmax/)
  })

  it('keeps the card while Show full history loads the longer list', async () => {
    companyPage([QUARTER, ANNUAL])
    const card = await screen.findByRole('complementary', { name: 'Insider activity' })
    await within(card).findByText('Net selling')
    api.getCompanyFilings.mockReturnValue(new Promise(() => {}))   // the full history never lands
    fireEvent.click(screen.getByRole('button', { name: 'Show full history' }))
    await settle()
    expect(screen.getByRole('complementary', { name: 'Insider activity' })).toBe(card)
    expect(within(card).getByText('Net selling')).toBeInTheDocument()
    expect(api.getInsiderActivity).toHaveBeenCalledTimes(1)
  })

  it('a foreign private issuer gets no card and no request, even for a beta account', async () => {
    companyPage([FOREIGN_ANNUAL])
    await waitFor(() => expect(api.getCurrentUserSafe).toHaveBeenCalled())
    await settle()
    expect(screen.queryByRole('complementary', { name: 'Insider activity' })).toBeNull()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()
  })
})

describe('the insider page: the company’s insider activity in full', () => {
  it('leads with the company and the way back to its filings', async () => {
    insidersPage([QUARTER, ANNUAL])
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Apple Inc. insider activity')
    const crumbs = within(screen.getByRole('navigation', { name: 'Breadcrumb' }))
    expect(crumbs.getByRole('link', { name: 'Apple Inc.' })).toHaveAttribute('href', '/company/AAPL')
    expect(crumbs.getByText('Insider activity')).toHaveAttribute('aria-current', 'page')
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'View filings' })).toHaveAttribute('href', '/company/AAPL')
  })

  it('shows a beta account the full panel: the window control and the trades', async () => {
    insidersPage([QUARTER, ANNUAL])
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Insider activity' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Time window' })).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(api.getInsiderActivity).toHaveBeenCalledWith('AAPL', 90)
  })

  it('holds the panel’s place with bones while the account check is out', async () => {
    api.getCurrentUserSafe.mockReturnValue(new Promise(() => {}))
    const filings = [QUARTER, ANNUAL]
    api.getCompany.mockResolvedValue(COMPANY)
    api.getCompanyFilings.mockResolvedValue(filings)
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InsidersPageClient initialCompany={COMPANY} initialFilings={filings} />
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('status', { name: 'Loading insider activity' })).toBeInTheDocument()
    expect(screen.queryByText('Insider activity is in beta')).toBeNull()
  })

  it('tells a guest it is in beta, with the way in and the way back, and asks nothing', async () => {
    insidersPage([QUARTER, ANNUAL], null)
    expect(await screen.findByRole('heading', { level: 2, name: 'Insider activity is in beta' })).toBeInTheDocument()
    const main = within(screen.getByRole('main'))
    expect(main.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login?redirect=%2Fcompany%2FAAPL%2Finsiders')
    expect(main.getByRole('link', { name: 'View filings' })).toHaveAttribute('href', '/company/AAPL')
    await settle()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()
  })

  it('tells an account that is not a beta tester the same, without a log-in link', async () => {
    insidersPage([QUARTER, ANNUAL], NOT_BETA)
    expect(await screen.findByRole('heading', { level: 2, name: 'Insider activity is in beta' })).toBeInTheDocument()
    const main = within(screen.getByRole('main'))
    expect(main.queryByRole('link', { name: 'Log in' })).toBeNull()
    expect(main.getByRole('link', { name: 'View filings' })).toHaveAttribute('href', '/company/AAPL')
    await settle()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()
  })

  it('an account check that fails outright says so, with Try again, and never tells the reader to log in', async () => {
    api.getCompany.mockResolvedValue(COMPANY)
    api.getCompanyFilings.mockResolvedValue([QUARTER, ANNUAL])
    api.getCurrentUserSafe.mockRejectedValueOnce(new ApiError(500, 'Internal Server Error')).mockResolvedValue(reader())
    api.getInsiderActivity.mockResolvedValue(ACTIVITY)
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InsidersPageClient initialCompany={COMPANY} initialFilings={[QUARTER, ANNUAL]} />
      </QueryClientProvider>,
    )
    const title = await screen.findByRole('heading', { level: 2, name: 'Couldn’t check your account' })
    const main = within(screen.getByRole('main'))
    expect(main.queryByRole('link', { name: 'Log in' })).toBeNull()
    expect(screen.queryByText('Insider activity is in beta')).toBeNull()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()

    fireEvent.click(main.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(title).not.toBeInTheDocument()
  })

  it('holds that card through another observer’s refetch of the account check: the bones never come back over it', async () => {
    api.getCompany.mockResolvedValue(COMPANY)
    api.getCompanyFilings.mockResolvedValue([QUARTER, ANNUAL])
    api.getCurrentUserSafe.mockRejectedValueOnce(new ApiError(500, 'Internal Server Error')).mockReturnValue(new Promise(() => {}))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <InsidersPageClient initialCompany={COMPANY} initialFilings={[QUARTER, ANNUAL]} />
      </QueryClientProvider>,
    )
    await screen.findByRole('heading', { level: 2, name: 'Couldn’t check your account' })
    // The site header observes the same query and refetches it when the window regains focus.
    await act(async () => {
      void client.refetchQueries({ queryKey: queryKeys.currentUser() })
      await settle()
    })
    expect(screen.getByRole('heading', { level: 2, name: 'Couldn’t check your account' })).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Loading insider activity' })).toBeNull()
  })

  it('stands from the first paint, named by the ticker over the card’s bones, and never as a full-page spinner', async () => {
    api.getCompany.mockReturnValue(new Promise(() => {}))
    api.getCurrentUserSafe.mockResolvedValue(reader())
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InsidersPageClient />
      </QueryClientProvider>,
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('AAPL insider activity')
    expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByRole('link', { name: 'AAPL' })).toHaveAttribute('href', '/company/AAPL')
    expect(within(screen.getByRole('main')).getByRole('status', { name: 'Loading insider activity' })).toBeInTheDocument()
    await settle()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()   // nothing is asked of a company not yet read
  })

  it('reads the company and its filings itself when the route seeds none, and titles the tab with the company', async () => {
    api.getCompany.mockResolvedValue(COMPANY)
    api.getCompanyFilings.mockResolvedValue([QUARTER, ANNUAL])
    api.getCurrentUserSafe.mockResolvedValue(reader())
    api.getInsiderActivity.mockResolvedValue(ACTIVITY)
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InsidersPageClient />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Apple Inc. insider activity')
    expect(api.getCompany).toHaveBeenCalledWith('AAPL')
    expect(document.title).toBe('Apple Inc. (AAPL) insider activity | EarningsNerd')
  })

  it.each([
    ['no such ticker', new ApiError(404, 'Not Found'), 'Company not found', 'Go back home'],
    ['a failed load', new ApiError(500, 'Internal Server Error'), 'Couldn’t load this company', 'Try again'],
  ])('%s: a card that says so, and no request to the insider endpoint', async (_, error, title, action) => {
    api.getCompany.mockRejectedValue(error)
    api.getCurrentUserSafe.mockResolvedValue(reader())
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InsidersPageClient />
      </QueryClientProvider>,
    )
    // The company read retries once on its own (a second apart) before it shows a failure.
    expect(await screen.findByRole('heading', { level: 1, name: title }, { timeout: 4000 })).toBeInTheDocument()
    expect(screen.getByRole(action === 'Try again' ? 'button' : 'link', { name: action })).toBeInTheDocument()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()
  })

  it('a company load that fails and then loads on Try again hands focus to the page’s heading', async () => {
    api.getCompany.mockRejectedValueOnce(new ApiError(500, 'Internal Server Error')).mockRejectedValueOnce(new ApiError(500, 'Internal Server Error')).mockResolvedValue(COMPANY)
    api.getCompanyFilings.mockResolvedValue([QUARTER, ANNUAL])
    api.getCurrentUserSafe.mockResolvedValue(reader())
    api.getInsiderActivity.mockResolvedValue(ACTIVITY)
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <InsidersPageClient />
      </QueryClientProvider>,
    )
    // The company read retries once on its own (a second apart) before it shows a failure.
    const retry = await screen.findByRole('button', { name: 'Try again' }, { timeout: 4000 })
    retry.focus()
    fireEvent.click(retry)
    const lead = await screen.findByRole('heading', { level: 1, name: /Apple Inc\./ }, { timeout: 4000 })
    await waitFor(() => expect(lead).toHaveFocus())
  })

  it('shows a beta account the foreign private issuer’s note, and asks nothing', async () => {
    insidersPage([FOREIGN_ANNUAL])
    expect(await screen.findByText(/not generally required for foreign private issuers/)).toBeInTheDocument()
    await settle()
    expect(api.getInsiderActivity).not.toHaveBeenCalled()
  })
})
