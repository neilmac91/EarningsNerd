import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import FilingPageClient from '@/app/filing/[id]/page-client'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import type { Filing } from '@/features/filings/api/filings-api'

/**
 * The change report needs no summary (it is computed from stored XBRL), and the company page's
 * "Open change report" links to /filing/{id}#what-changed whether or not the filing has one. So where
 * the filing page settles without a summary (the signup gate, a run that ended in an error or at the
 * monthly limit), the report is a card of its own with the id the link names, and lands it.
 */

const state = vi.hoisted(() => ({
  user: null as { id: number } | null,
  generation: {} as Record<string, unknown>,
  getWhatChanged: vi.fn(),
  getFiling: vi.fn(),
}))
vi.mock('next/navigation', () => ({ useParams: () => ({ id: '42' }), useRouter: () => ({ back: vi.fn(), push: vi.fn() }) }))
vi.mock('@/lib/api/client', () => ({ default: { get: vi.fn(), post: vi.fn() }, getApiUrl: vi.fn() }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: () => Promise.resolve(state.user) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getSubscriptionStatus: () => Promise.resolve({ is_pro: false }) }))
vi.mock('@/features/filings/api/filings-api', () => ({
  getFiling: state.getFiling,
}))
vi.mock('@/features/summaries/api/summaries-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/summaries/api/summaries-api')>()),
  getWhatChanged: state.getWhatChanged,
}))
vi.mock('@/features/summaries/hooks/useSummaryGeneration', () => ({
  useSummaryGeneration: () => ({ summary: null, hasSummaryContent: false, summaryLoading: false, streamingText: '', ...state.generation }),
}))
vi.mock('@/lib/analytics', () => ({ default: new Proxy({}, { get: () => () => {} }) }))
vi.mock('@/features/filings/components/copilot/FilingWorkspace', () => ({ default: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock('@/features/filings/components/copilot/FilingViewerContext', () => ({ FilingViewerProvider: ({ children }: { children: ReactNode }) => <>{children}</> }))
vi.mock('@/features/filings/components/copilot/AskAboutSelection', () => ({ default: () => null }))
vi.mock('@/features/filings/components/copilot/AskCopilotRail', () => ({ default: () => null }))
vi.mock('@/features/filings/components/copilot/FilingViewer', () => ({ default: () => null }))

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
const FAILED = 'The filing could not be summarized right now.'
const LIMIT = "You've reached your monthly limit. Upgrade to Pro for unlimited summaries."
const FILING: Filing = {
  id: 42, filing_type: '10-K', filing_date: '2025-10-31', accession_number: 'test-filing',
  sec_url: 'https://www.sec.gov/Archives/', document_url: 'https://www.sec.gov/Archives/filing.htm',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
}
const clients: QueryClient[] = []

function mount(initialChangeReport?: ChangeReport, initialFiling?: Filing) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(client)
  return render(
    <QueryClientProvider client={client}>
      <FilingPageClient initialChangeReport={initialChangeReport} initialFiling={initialFiling} />
    </QueryClientProvider>,
  )
}

const jsdomScrollIntoView = Element.prototype.scrollIntoView
// jsdom has no scrollIntoView; record which element each call scrolls to.
const scrolledTo = () => vi.mocked(Element.prototype.scrollIntoView).mock.contexts.map((el) => (el as Element).id)

beforeEach(() => {
  state.user = null
  state.generation = {}
  state.getFiling.mockReset().mockResolvedValue(FILING)
  state.getWhatChanged.mockReturnValue(new Promise(() => {}))
  window.history.replaceState(null, '', '#what-changed')
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => {
  cleanup()
  clients.splice(0).forEach((client) => client.clear())
  onlineManager.setOnline(true)
  vi.clearAllMocks()
  window.history.replaceState(null, '', window.location.pathname)
  Element.prototype.scrollIntoView = jsdomScrollIntoView
})

describe('filing read recovery', () => {
  it('keeps an initial offline read unresolved rather than declaring the filing missing', () => {
    onlineManager.setOnline(false)
    mount()
    expect(screen.getByRole('status')).toHaveTextContent('Loading filing')
    expect(screen.queryByRole('heading', { name: 'Filing not found' })).not.toBeInTheDocument()
    expect(state.getFiling).not.toHaveBeenCalled()
  })

  it.each([new Error('offline'), { status: 503 }, { status: 403 }])('offers local recovery for a read failure (%s)', async (error) => {
    state.getFiling.mockRejectedValueOnce(error)
    mount()
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this filing.')
    expect(screen.queryByRole('heading', { name: 'Filing not found' })).not.toBeInTheDocument()
    let finish!: (filing: Filing) => void
    state.getFiling.mockImplementationOnce(() => new Promise<Filing>((resolve) => { finish = resolve }))
    const user = userEvent.setup()
    const retry = screen.getByRole('button', { name: 'Try again' })
    retry.focus()
    await user.keyboard('{Enter}{Enter}')
    expect(state.getFiling).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load this filing.')
    expect(retry).toHaveFocus()
    await act(async () => finish(FILING))
    expect(await screen.findByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('main', { name: 'Filing research' })).toHaveFocus())
  })

  it.each([undefined, FILING])('uses not-found for a confirmed missing filing, including an older seed (%s)', async (seed) => {
    state.getFiling.mockRejectedValue({ status: 404 })
    mount(undefined, seed)
    expect(await screen.findByRole('heading', { name: 'Filing not found' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Apple Inc.' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go back home' })).toBeInTheDocument()
  })

  it('keeps the server-seeded filing available when its refresh fails', async () => {
    state.getFiling.mockRejectedValue(new Error('offline'))
    mount(REPORT, FILING)
    expect(await screen.findByRole('alert')).toHaveTextContent('Showing the last loaded filing.')
    expect(screen.getByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'What changed' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('the change report on a filing with no summary', () => {
  it('shows under the signup gate for a signed-out visitor, and the link lands on it', async () => {
    mount(REPORT)
    await screen.findByRole('heading', { name: 'Summaries need an account' })
    expect(screen.getByRole('region', { name: 'What changed' })).toHaveAttribute('id', 'what-changed')
    expect(scrolledTo()).toEqual(['what-changed'])
  })

  it('arrives under the gate when the page has no server read of it', async () => {
    state.getWhatChanged.mockResolvedValue(REPORT)
    mount()
    await screen.findByRole('region', { name: 'What changed' })
    expect(state.getWhatChanged).toHaveBeenCalledWith(42)
    expect(scrolledTo()).toEqual(['what-changed'])
  })

  it.each([
    ['an error', FAILED, 'Generation interrupted'],
    ['the monthly limit', LIMIT, "You've hit this month's free limit"],
  ])('stays under a run that ended in %s', async (_, error, title) => {
    state.user = { id: 7 }
    state.generation = { hasStartedGeneration: true, generationError: error, activeErrorMessage: error, streamingStage: 'error' }
    mount(REPORT)
    await screen.findByRole('heading', { name: title })
    expect(screen.getByRole('region', { name: 'What changed' })).toHaveAttribute('id', 'what-changed')
    expect(scrolledTo()).toEqual(['what-changed'])
  })

  it('waits for a run in flight, whose summary holds the report as a section', async () => {
    state.user = { id: 7 }
    state.generation = { isStreaming: true, hasStartedGeneration: true, streamingStage: 'summarizing' }
    mount(REPORT)
    await screen.findByRole('progressbar')
    expect(screen.queryByRole('region', { name: 'What changed' })).toBeNull()
    expect(scrolledTo()).toEqual([])
  })

  it('shows nothing under the gate when the report has nothing to say', async () => {
    mount({ ...REPORT, has_changes: false })
    await screen.findByRole('heading', { name: 'Summaries need an account' })
    expect(screen.queryByRole('region', { name: 'What changed' })).toBeNull()
  })
})
