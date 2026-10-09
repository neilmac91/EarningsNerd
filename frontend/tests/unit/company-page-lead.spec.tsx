import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import CompanyPageClient from '@/app/company/[ticker]/page-client'

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
    const open = within(header).getByRole('link', { name: 'Summarize latest filing' })
    expect(open).toHaveAttribute('href', '/filing/12')
    await waitFor(() => expect(api.getSummary).toHaveBeenCalledWith(12))
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

  // A row the filing page will not show as a summary is not one: a placeholder it treats as generation
  // in progress, and a stored failure it shows as "Summary temporarily unavailable".
  it.each([
    ['a placeholder', { business_overview: 'Generating summary...' }],
    ['a writer error', { business_overview: 'Apple designs devices.', raw_summary: { writer_error: 'timeout' } }],
    ['the fallback body', { business_overview: 'Summary temporarily unavailable. Please retry.' }],
  ])('says nothing is ready while the stored summary is %s', async (_, stored) => {
    api.getSummary.mockResolvedValue({ id: 5, filing_id: 12, ...stored })
    renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL])
    const header = screen.getByRole('banner')
    await waitFor(() => expect(api.getSummary).toHaveBeenCalledWith(12))
    expect(await within(header).findByRole('link', { name: 'Summarize latest filing' })).toHaveAttribute('href', '/filing/12')
    expect(within(header).queryByText('summary ready')).toBeNull()
  })

  it('keeps the watchlist a secondary action with a visible label for a signed-in visitor', async () => {
    api.getSummary.mockResolvedValue(null)
    const { container } = renderPage([QUARTER, ANNUAL, PRIOR_ANNUAL], { signedIn: true })
    const star = await screen.findByRole('button', { name: 'Add to watchlist' })
    expect(star).toHaveAttribute('aria-pressed', 'false')
    expect(star).not.toHaveAttribute('aria-label')
    expect(star.className).not.toMatch(/(^|\s)bg-brand(\s|$)/)
    expect(primaryActions(container)).toEqual([screen.getByRole('link', { name: 'Summarize latest filing' })])
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
