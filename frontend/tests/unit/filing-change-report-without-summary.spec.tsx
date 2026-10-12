import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import FilingPageClient from '@/app/filing/[id]/page-client'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'

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
}))
vi.mock('next/navigation', () => ({ useParams: () => ({ id: '42' }), useRouter: () => ({ back: vi.fn(), push: vi.fn() }) }))
vi.mock('@/lib/api/client', () => ({ default: { get: vi.fn(), post: vi.fn() }, getApiUrl: vi.fn() }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: () => Promise.resolve(state.user) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getSubscriptionStatus: () => Promise.resolve({ is_pro: false }) }))
vi.mock('@/features/filings/api/filings-api', () => ({
  getFiling: () => Promise.resolve({ id: 42, filing_type: '10-K', filing_date: '2025-10-31', company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' } }),
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

function mount(initialChangeReport?: ChangeReport) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <FilingPageClient initialChangeReport={initialChangeReport} />
    </QueryClientProvider>,
  )
}

const jsdomScrollIntoView = Element.prototype.scrollIntoView
// jsdom has no scrollIntoView; record which element each call scrolls to.
const scrolledTo = () => vi.mocked(Element.prototype.scrollIntoView).mock.contexts.map((el) => (el as Element).id)

beforeEach(() => {
  state.user = null
  state.generation = {}
  state.getWhatChanged.mockReturnValue(new Promise(() => {}))
  window.history.replaceState(null, '', '#what-changed')
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.history.replaceState(null, '', window.location.pathname)
  Element.prototype.scrollIntoView = jsdomScrollIntoView
})

describe('the change report on a filing with no summary', () => {
  it('shows under the signup gate for a signed-out visitor, and the link lands on it', async () => {
    mount(REPORT)
    await screen.findByRole('heading', { name: 'Create a free account to analyze this filing' })
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
    await screen.findByRole('heading', { name: 'Create a free account to analyze this filing' })
    expect(screen.queryByRole('region', { name: 'What changed' })).toBeNull()
  })
})
