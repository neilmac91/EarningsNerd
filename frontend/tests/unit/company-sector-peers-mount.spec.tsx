/* =============================================================================
   company-sector-peers-mount.spec.tsx: the Sector peers panel on the company page (E251)
   -----------------------------------------------------------------------------
   CompanyPageClient as the route renders it, with the flag the panel ships under on (Vitest's env sets
   NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS), its reads answered here and the peers from the fixture
   (tests/unit/fixtures/peers-cohorts.json). Two of E251's gaps, each a gate:
   - keyed by ticker: a metric picked on one company is gone on the next, which opens at the default metric on its own
     answer, even where that answer is already in the cache (as after an earlier visit) and the panel shows at once;
   - inside a ChartErrorBoundary: a card that cannot be drawn leaves the filings and the boundary's own card in its
     place, with the panel's spacing, and a move to another company clears it (the boundary never resets on its own, so
     the key sits on it).
   And its place: after the filings, the last section of <main>. The page as CI ships it, the panel mounted, is
   tests/e2e/company-sector-peers.spec.ts's.
============================================================================= */
import { readFileSync } from 'node:fs'
import type { ComponentProps, ReactNode } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import type { PeerComparisonResponse } from '@/features/peers/api/peers-api'
import { queryKeys } from '@/lib/queryKeys'
import type { PeerFixture } from './chartPlan'

const api = vi.hoisted(() => ({
  getWatchlist: vi.fn(),
  getCompany: vi.fn(),
  getCompanyFilings: vi.fn(),
  getSummary: vi.fn(),
  getWhatChanged: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  getPeers: vi.fn(),
}))
const route = vi.hoisted(() => ({ ticker: 'aapl' }))
// The ticker whose card cannot be drawn: it throws as it renders, as a chart the engine cannot lay out would.
const broken = vi.hoisted(() => ({ ticker: null as string | null }))
vi.mock('@/features/watchlist/api/watchlist-api', () => ({ addToWatchlist: vi.fn(), removeFromWatchlist: vi.fn(), getWatchlist: api.getWatchlist }))
vi.mock('@/features/companies/api/companies-api', () => ({ getCompany: api.getCompany }))
vi.mock('@/features/filings/api/filings-api', () => ({ getCompanyFilings: api.getCompanyFilings }))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getSummary: api.getSummary, getWhatChanged: api.getWhatChanged }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/features/peers/api/peers-api', () => ({ getPeers: api.getPeers }))
vi.mock('@/features/peers/components/SectorPeersCard', async (importOriginal) => {
  const { default: Card } = await importOriginal<typeof import('@/features/peers/components/SectorPeersCard')>()
  return {
    default: (props: ComponentProps<typeof Card>) => {
      if (props.ticker === broken.ticker) throw new Error('the chart could not be drawn')
      return <Card {...props} />
    },
  }
})
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_FINANCIAL_CHARTS: true,
  ENABLE_INSIDER_ACTIVITY: false,
}))
vi.mock('@/lib/analytics', () => ({ default: { watchlistAdded: vi.fn(), watchlistRemoved: vi.fn(), companyViewed: vi.fn() } }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('next/navigation', () => ({
  useParams: () => ({ ticker: route.ticker }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => `/company/${route.ticker}`,
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => <a href={href} {...props}>{children}</a>,
}))

import CompanyPageClient from '@/app/company/[ticker]/page-client'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/peers-cohorts.json', 'utf8')) as PeerFixture
const answerOf = (name: string): PeerComparisonResponse => structuredClone(FIXTURE.cases[name].response)

const COMPANIES: Record<string, Company> = {
  AAPL: { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
  MSFT: { id: 2, cik: '789019', ticker: 'MSFT', name: 'Microsoft Corp', exchange: 'NASDAQ' },
}
const filing = (id: number, cik: string, filing_type: string, filed: string, report: string): Filing => ({
  id,
  filing_type,
  filing_date: `${filed}T00:00:00+00:00`,
  report_date: `${report}T00:00:00+00:00`,
  accession_number: `000${cik}-${id}`,
  document_url: `https://www.sec.gov/doc/${id}`,
  sec_url: `https://www.sec.gov/edgar/${id}`,
})
const FILINGS: Record<string, Filing[]> = {
  AAPL: [filing(12, '320193', '10-Q', '2026-01-30', '2025-12-27'), filing(11, '320193', '10-K', '2025-10-31', '2025-09-27')],
  MSFT: [filing(22, '789019', '10-Q', '2026-01-28', '2025-12-31'), filing(21, '789019', '10-K', '2025-07-30', '2025-06-30')],
}
/** Each company's cohort on each metric: Apple's is the spread, Microsoft's the near-equal case. */
const PEERS: Record<string, Record<string, PeerComparisonResponse>> = {
  AAPL: { revenue: answerOf('spread'), net_income: { ...answerOf('spread'), concept: 'net_income' } },
  MSFT: { revenue: answerOf('near-equal'), net_income: { ...answerOf('near-equal'), concept: 'net_income' } },
}

// The card's module, the engine with it, loads once before the cases, as its chunk loads once a page: the first
// dynamic import transforms the engine, which under a full suite's load outlasts a find's default wait.
beforeAll(async () => {
  await import('@/features/peers/components/SectorPeersCard')
})

afterEach(() => {
  route.ticker = 'aapl'
  broken.ticker = null
  vi.clearAllMocks()
})

function answerReads() {
  api.getCompany.mockImplementation((ticker: string) => Promise.resolve(COMPANIES[ticker.toUpperCase()]))
  api.getCompanyFilings.mockImplementation((ticker: string) => Promise.resolve(FILINGS[ticker.toUpperCase()]))
  api.getCurrentUserSafe.mockResolvedValue(null)
  api.getWatchlist.mockResolvedValue([])
  api.getSummary.mockResolvedValue(null)
  api.getWhatChanged.mockResolvedValue(null)
  api.getPeers.mockImplementation((ticker: string, metric: string) => Promise.resolve(PEERS[ticker][metric]))
}

/** The page for a company, on the route's ticker. */
const page = (client: QueryClient, ticker: 'AAPL' | 'MSFT') => (
  <QueryClientProvider client={client}>
    <CompanyPageClient initialCompany={COMPANIES[ticker]} initialFilings={FILINGS[ticker]} />
  </QueryClientProvider>
)
const newClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
const panelCard = async () => (await screen.findByRole('heading', { level: 2, name: 'Sector peers' }, { timeout: 4000 })).closest('section') as HTMLElement
const picker = (scope: HTMLElement) => within(scope).getByRole('combobox', { name: 'Metric' })
const rankLine = (scope: HTMLElement) => within(scope).getByText(/ranks #/).closest('p')

describe('the Sector peers panel on the company page (E251)', () => {
  it('sits after the filings, the last section of <main>', async () => {
    answerReads()
    render(page(newClient(), 'AAPL'))
    const section = await panelCard()
    const filings = screen.getByRole('heading', { level: 2, name: 'SEC filings' }).closest('section')!
    expect(filings.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING, 'after the filings').toBeTruthy()
    expect(screen.getByRole('main').lastElementChild).toBe(section)
    expect(section.className.split(/\s+/)).toContain('mt-8')
  })

  it('starts afresh on another company: a metric picked on one is gone on the next, which opens on its own default answer', async () => {
    answerReads()
    const client = newClient()
    // Microsoft's answer is in the cache, as after an earlier visit, so its panel shows the moment the page moves.
    client.setQueryData(queryKeys.peers('MSFT', 'revenue'), PEERS.MSFT.revenue)
    const { rerender } = render(page(client, 'AAPL'))
    const apple = await panelCard()
    fireEvent.change(picker(apple), { target: { value: 'net_income' } })
    await waitFor(() => expect(rankLine(apple)).toHaveTextContent('SUBX ranks #6 of 11 on net income'))
    expect(api.getPeers).toHaveBeenCalledWith('AAPL', 'net_income')

    route.ticker = 'msft'
    rerender(page(client, 'MSFT'))
    const microsoft = await panelCard()
    expect(picker(microsoft)).toHaveValue('revenue')
    expect(rankLine(microsoft)).toHaveTextContent('NEQD ranks #4 of 11 on revenue')
    expect(api.getPeers).not.toHaveBeenCalledWith('MSFT', 'net_income')
  })

  it('keeps a chart that cannot be drawn inside its boundary: the filings stay, the boundary’s card stands in with the panel’s spacing, and another company clears it', async () => {
    answerReads()
    broken.ticker = 'AAPL'
    // React logs what the boundary catches, and rethrows it through a window error event that jsdom reports unless it is
    // handled; keep the output quiet.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const handled = (event: ErrorEvent) => event.preventDefault()
    window.addEventListener('error', handled)
    try {
      const client = newClient()
      const { rerender } = render(page(client, 'AAPL'))
      const fallback = await screen.findByText('This chart could not be drawn.')
      expect(fallback.parentElement!.className.split(/\s+/)).toContain('mt-8')
      expect(screen.getByRole('heading', { level: 2, name: 'SEC filings' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Sector peers' })).toBeNull()

      route.ticker = 'msft'
      rerender(page(client, 'MSFT'))
      const microsoft = await panelCard()
      expect(rankLine(microsoft)).toHaveTextContent('NEQD ranks #4 of 11 on revenue')
      expect(screen.queryByText('This chart could not be drawn.')).toBeNull()
    } finally {
      window.removeEventListener('error', handled)
      consoleError.mockRestore()
    }
  })
})
