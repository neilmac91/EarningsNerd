import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SummaryDisplay } from '@/features/summaries/components/SummaryDisplay'
import type { Filing } from '@/features/filings/api/filings-api'
import type { ChangeReport, Summary } from '@/features/summaries/api/summaries-api'

/**
 * What changed is in the FIRST render (2026-10 review of the critique PR): the filing page reads the
 * change report on the server beside the filing and summary and seeds it, so the section is in the
 * HTML. Inserted after a client fetch instead, it pushed every later section down by its height and
 * renumbered the table of contents under a reader.
 */

const api = vi.hoisted(() => ({ getWhatChanged: vi.fn() }))
const server = vi.hoisted(() => ({
  fetchFilingServer: vi.fn(),
  fetchFilingSummaryServer: vi.fn(),
  fetchWhatChangedServer: vi.fn(),
  client: vi.fn(),
}))
vi.mock('@/features/summaries/api/summaries-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/summaries/api/summaries-api')>()),
  getWhatChanged: api.getWhatChanged,
}))
vi.mock('@/features/summaries/hooks/useSummaryExports', () => ({
  useSummaryExports: () => ({ exportPdf: vi.fn(), exportCsv: vi.fn() }),
}))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  ENABLE_FINANCIAL_CHARTS: false,
}))
vi.mock('@/lib/serverApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/serverApi')>()),
  fetchFilingServer: server.fetchFilingServer,
  fetchFilingSummaryServer: server.fetchFilingSummaryServer,
  fetchWhatChangedServer: server.fetchWhatChangedServer,
}))
vi.mock('@/app/filing/[id]/page-client', () => ({
  default: (props: Record<string, unknown>) => {
    server.client(props)
    return null
  },
}))

const FILING: Filing = {
  id: 42,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  report_date: '2025-09-27T00:00:00+00:00',
  accession_number: '0000320193-25-000079',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
}
const SUMMARY: Summary = {
  id: 91,
  filing_id: 42,
  business_overview: 'Apple designs devices.',
  rendered_sections: [
    { id: 'executive-assessment', title: 'Executive assessment', blocks: [{ kind: 'paragraph', text: 'Revenue grew.' }] },
    {
      id: 'financial-highlights',
      title: 'Financial highlights',
      blocks: [{ kind: 'metrics', headers: ['Metric', 'Current Period'], rows: [['Revenue', '$416.2B']], metric_rows: [{ metric: 'Revenue', current_period: '$416.2B' }] }],
    },
    { id: 'investment-risks-concerns', title: 'Risks', role: 'risks', blocks: [] },
  ],
} as Summary
const REPORT: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Year over year',
  prior_filing: { filing_id: 7, filing_type: '10-K', filing_date: '2024-11-01T00:00:00+00:00', period_end_date: '2024-09-28T00:00:00+00:00' },
  metrics: {
    headline: 'Revenue up 6.4%',
    items: [{ metric: 'revenue', label: 'Revenue', direction: 'up', pct: 6.4, current: 416e9, prior: 391e9, display: '+6.4%', tone: 'gain' }],
    data_quality: 'ok',
  },
  reporting_currency: 'USD',
  risks: null,
  key_changes: null,
  has_changes: true,
}

function display(initialChangeReport?: ChangeReport, summary: Summary = SUMMARY) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return render(
    <SummaryDisplay
      summary={summary}
      filing={FILING}
      isPro={false}
      isSaved={false}
      isAuthenticated={false}
      saveMutation={{ mutate: vi.fn(), isPending: false }}
      onAsk={vi.fn()}
      initialChangeReport={initialChangeReport}
    />,
    { wrapper },
  )
}

const tocTitles = () =>
  within(screen.getByRole('navigation', { name: 'Summary sections' }))
    .getAllByRole('link')
    .map((a) => a.textContent)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('What changed in the first render', () => {
  it('renders the seeded report as section 03 at once, with no client fetch', () => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    display(REPORT)
    expect(screen.getByRole('region', { name: 'What changed' })).toBeInTheDocument()
    expect(tocTitles()).toEqual(['01Executive assessment', '02Financial highlights', '03What changed', '04Risks'])
    expect(api.getWhatChanged).not.toHaveBeenCalled()
  })

  it('without a seed it can only arrive later (the client fetch the server read replaces)', () => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    display(undefined)
    expect(screen.queryByRole('region', { name: 'What changed' })).toBeNull()
    expect(tocTitles()).toEqual(['01Executive assessment', '02Financial highlights', '03Risks'])
    expect(api.getWhatChanged).toHaveBeenCalledWith(42)
  })

  it('the page reads it on the server beside the filing and summary, and seeds the client', async () => {
    const { default: FilingPage } = await import('@/app/filing/[id]/page')
    server.fetchFilingServer.mockResolvedValue({ status: 'ok', data: FILING })
    server.fetchFilingSummaryServer.mockResolvedValue({ status: 'ok', data: SUMMARY })
    server.fetchWhatChangedServer.mockResolvedValue({ status: 'ok', data: REPORT })
    render(await FilingPage({ params: Promise.resolve({ id: '42' }) }))
    expect(server.fetchWhatChangedServer).toHaveBeenCalledWith(42)
    expect(server.client).toHaveBeenCalledWith(expect.objectContaining({ initialSummary: SUMMARY, initialChangeReport: REPORT }))
  })

  it('leaves the client to fetch it when the server read is unavailable', async () => {
    const { default: FilingPage } = await import('@/app/filing/[id]/page')
    server.fetchFilingServer.mockResolvedValue({ status: 'ok', data: FILING })
    server.fetchFilingSummaryServer.mockResolvedValue({ status: 'ok', data: SUMMARY })
    server.fetchWhatChangedServer.mockResolvedValue({ status: 'unavailable' })
    render(await FilingPage({ params: Promise.resolve({ id: '42' }) }))
    expect(server.client).toHaveBeenCalledWith(expect.objectContaining({ initialChangeReport: undefined }))
  })
})

describe('the summary page outline', () => {
  it('sets the Ask callout as a sibling of the sections (h2), not a subsection of the last one', () => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    display(REPORT)
    const outline = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(outline).toEqual(['Executive assessment', 'Financial highlights', 'What changed', 'Risks', 'Ask AAPL’s 10-K anything'])
  })
})

describe('as a card, where the summary has no sections to hold it', () => {
  // rendered_sections: [] takes the markdown fallback, where the change report is a card under the
  // markdown, and a stored summary that failed shows its error card with the report card under it.
  // The company page's "Open change report" (/filing/{id}#what-changed) lands on the card in both.
  const LEGACY = { ...SUMMARY, rendered_sections: [] } as Summary
  const jsdomScrollIntoView = Element.prototype.scrollIntoView
  // jsdom has no scrollIntoView; record which element each call scrolls to.
  const scrolledTo = () => vi.mocked(Element.prototype.scrollIntoView).mock.contexts.map((el) => (el as Element).id)

  beforeEach(() => {
    window.history.replaceState(null, '', '#what-changed')
    Element.prototype.scrollIntoView = vi.fn()
  })
  afterEach(() => {
    window.history.replaceState(null, '', window.location.pathname)
    Element.prototype.scrollIntoView = jsdomScrollIntoView
  })

  it('gives the card the id the link names, and lands on it', () => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    display(REPORT, LEGACY)
    expect(screen.queryByRole('navigation', { name: 'Summary sections' })).toBeNull()
    expect(screen.getByRole('region', { name: 'What changed' })).toHaveAttribute('id', 'what-changed')
    expect(scrolledTo()).toEqual(['what-changed'])
  })

  it('lands on it when the report arrives after the summary', async () => {
    api.getWhatChanged.mockResolvedValue(REPORT)
    display(undefined, LEGACY)
    expect(scrolledTo()).toEqual([])
    await screen.findByRole('region', { name: 'What changed' })
    expect(scrolledTo()).toEqual(['what-changed'])
  })

  it('shows a real summary that mentions generating summaries as the summary, not the error card', () => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    display(REPORT, { ...LEGACY, business_overview: 'Apple reworked its revenue-generating summary reports.' } as Summary)
    expect(screen.queryByRole('heading', { name: 'Summary temporarily unavailable' })).toBeNull()
    expect(screen.getByText('Apple reworked its revenue-generating summary reports.')).toBeInTheDocument()
  })

  it.each([
    ['its fallback body', { ...LEGACY, business_overview: 'Summary temporarily unavailable. Please retry.' }],
    ['a writer error over its sections', { ...SUMMARY, raw_summary: { writer_error: 'timeout' } }],
    ['placeholder filler', { ...LEGACY, business_overview: 'Summary generation requires OpenAI API key. Please configure OPENAI_API_KEY in your .env file.' }],
  ])('stays under a stored summary that failed (%s)', (_, failed) => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    display(REPORT, failed as Summary)
    expect(screen.getByRole('heading', { name: 'Summary temporarily unavailable' })).toBeInTheDocument()
    // The error card, never the stored text: "requires OpenAI API key" is operator configuration.
    expect(screen.queryByText(/OPENAI_API_KEY/)).toBeNull()
    expect(screen.queryByRole('navigation', { name: 'Summary sections' })).toBeNull()
    expect(screen.getByRole('region', { name: 'What changed' })).toHaveAttribute('id', 'what-changed')
    expect(scrolledTo()).toEqual(['what-changed'])
  })
})
