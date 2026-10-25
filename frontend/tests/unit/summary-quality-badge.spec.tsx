import { cleanup, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SummaryDisplay } from '@/features/summaries/components/SummaryDisplay'
import type { Filing } from '@/features/filings/api/filings-api'
import type { Summary } from '@/features/summaries/api/summaries-api'

const flags = vi.hoisted(() => ({ ENABLE_QUALITY_BADGE: true }))
vi.mock('@/lib/featureFlags', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/featureFlags')>(),
  get ENABLE_QUALITY_BADGE() { return flags.ENABLE_QUALITY_BADGE },
  ENABLE_FINANCIAL_CHARTS: false,
}))
vi.mock('@/features/summaries/hooks/useWhatChanged', () => ({
  useWhatChanged: () => ({ report: null, provisional: false }),
}))
vi.mock('@/features/summaries/hooks/useSummaryExports', () => ({
  useSummaryExports: () => ({ exportPdf: vi.fn(), exportCsv: vi.fn() }),
}))

const filing: Filing = {
  id: 42, filing_type: '10-K', filing_date: '2025-10-31', accession_number: 'test-accession',
  document_url: 'https://www.sec.gov/Archives/test/doc.htm', sec_url: 'https://www.sec.gov/Archives/test/',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
}
const clients: QueryClient[] = []
function show(raw_summary: Summary['raw_summary'], demoMode = false, business_overview = 'The filing describes the business and its financial results.') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(client)
  render(<QueryClientProvider client={client}>
    <SummaryDisplay filing={filing}
      summary={{ id: 91, filing_id: 42, business_overview, raw_summary, rendered_sections: [] }}
      demoMode={demoMode} isAuthenticated isPro isSaved={false}
      saveMutation={{ mutate: vi.fn(), isPending: false }} onAsk={vi.fn()} onRetry={vi.fn()} />
  </QueryClientProvider>)
}

afterEach(() => {
  cleanup()
  clients.splice(0).forEach(client => client.clear())
  flags.ENABLE_QUALITY_BADGE = true
})

// Coverage is visible in examples as in ordinary summaries. The short label never contains
// an unbounded reason; every recorded reason has readable details in a native disclosure.
// Keep every server reason in `firsts`: test_quality_grounding_presence.py ties this fixture
// to the backend's emitted strings. Browser reflow is measured separately, not by a character cap.
const firsts = [
  ['financial figures not grounded in SEC XBRL data'],
  ['filing grounding unavailable: no usable excerpt or numeric XBRL data'],
  ['only 3/9 sections populated'],
  ['12 summary figure(s) not traceable to filing data'],
]
const explanations = [
  'The automatic check did not find the filed revenue or net income in the summary.',
  'The filing’s text and figures were unavailable to check against.',
  'Only 3 of 9 summary sections contain information.',
  'The automatic check could not trace 12 summary figures to the filing’s data.',
]

for (const demo of [false, true]) {
  describe(`${demo ? 'example' : 'ordinary'} summary coverage`, () => {
    it.each(firsts.map((reasons, i) => ({ reasons, explanation: explanations[i] })))(
      'keeps $reasons visible with full, human-readable details', ({ reasons, explanation }) => {
        show({ quality: { tier: 'partial', reasons } }, demo)
        const coverage = screen.getByRole('group', { name: 'Summary coverage' })
        expect(within(coverage).getByText('Partial coverage')).toBeVisible()
        expect(coverage.querySelector('[title]')).toBeNull()
        const disclosure = coverage.querySelector('details')!
        expect(disclosure.querySelector('summary')).toHaveTextContent('Coverage details')
        expect(within(disclosure).getByText(explanation)).toBeInTheDocument()
        expect(within(disclosure).getByText('Coverage does not verify every claim. Check the cited sources and the original filing.')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Regenerate summary' }) !== null).toBe(!demo)
      },
    )

    it('reports the full verdict as automatic checks, without claiming every claim was verified', () => {
      show({ quality: { tier: 'full', reasons: [], covered_count: 4, total_count: 9 } }, demo)
      expect(screen.getByText('Full summary')).toBeVisible()
      expect(screen.getByText('Coverage does not verify every claim. Check the cited sources and the original filing.')).toBeInTheDocument()
      expect(screen.getByText('This summary passed the automatic coverage checks when it was generated.')).toBeInTheDocument()
    })

    it.each([undefined, { tier: 'unrecognized' }])('states unknown when the coverage verdict is %s', quality => {
      show({ quality }, demo)
      expect(screen.getByText('Coverage unknown')).toBeVisible()
      expect(screen.getByText('No coverage check result is available for this summary.')).toBeInTheDocument()
      expect(screen.queryByText('Full summary')).not.toBeInTheDocument()
    })
  })
}

it.each([undefined, { tier: 'full' }])('honors a recorded partial generation over quality %s', quality => {
  show({ status: 'partial', quality })
  expect(screen.getByText('Partial coverage')).toBeVisible()
  expect(screen.getByText('No further coverage details were recorded.')).toBeInTheDocument()
  expect(screen.queryByText('Full summary')).not.toBeInTheDocument()
})

it('keeps every reason in the disclosure without showing unknown internal diagnostics', () => {
  show({ quality: { tier: 'partial', reasons: [...firsts.flat(), 'internal stack trace: host /private/path'] } })
  const disclosure = screen.getByRole('group', { name: 'Summary coverage' }).querySelector('details')!
  for (const explanation of explanations) expect(within(disclosure).getByText(explanation)).toBeInTheDocument()
  expect(within(disclosure).getByText('A coverage issue was recorded, but its details are unavailable.')).toBeInTheDocument()
  expect(screen.queryByText(/internal stack trace/)).not.toBeInTheDocument()
})

it('preserves the feature switch and stored-failure recovery', () => {
  flags.ENABLE_QUALITY_BADGE = false
  show({ quality: { tier: 'full' } })
  expect(screen.queryByRole('group', { name: 'Summary coverage' })).not.toBeInTheDocument()
  cleanup()
  flags.ENABLE_QUALITY_BADGE = true
  show({ quality: { tier: 'full' } }, true, 'Summary temporarily unavailable. Please retry.')
  expect(screen.getByRole('heading', { name: 'This summary did not finish' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible()
  expect(screen.queryByRole('group', { name: 'Summary coverage' })).not.toBeInTheDocument()
})
