import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do — stub it (same as fundamentals-trend-chart).
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))
// react-markdown is ESM-heavy; the teaser only needs the text to land in the DOM.
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}))
vi.mock('remark-gfm', () => ({ default: () => null }))
// PeekLocked's UpgradeModal calls useRouter — no app router is mounted under vitest.
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
// More than six periods makes the sample contract observable at both real call sites.
vi.mock('@/features/analysis/demo/demo-analysis.json', async importOriginal => {
  const original = await importOriginal<typeof import('@/features/analysis/demo/demo-analysis.json')>()
  return { default: { ...original.default, dataset: { ...original.default.dataset,
    periods: [...original.default.dataset.periods, { key: 'FY2025', fiscal_year: 2025, fiscal_period: 'FY', period_end: '2025-12-31' }],
  } } }
})

import AnalysisTeaser from '@/features/analysis/components/AnalysisTeaser'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'

const originalFetch = global.fetch

describe('AnalysisTeaser (free-user lock)', () => {
  afterEach(() => {
    global.fetch = originalFetch
  })

  it('renders the locked sample without a single network call', () => {
    const fetchSpy = vi.fn()
    global.fetch = fetchSpy as unknown as typeof fetch

    render(<AnalysisTeaser forTicker="MSFT" />)

    // The PeekLocked chrome + upgrade CTA are present…
    expect(screen.getByRole('button', { name: /upgrade to unlock/i })).toBeInTheDocument()
    // …the sample is honestly labelled and personalized…
    expect(screen.getByText(/Sample: Apple Inc\./)).toBeInTheDocument()
    expect(screen.getByText(/Upgrade to run it for MSFT/)).toBeInTheDocument()
    // …and NO backend/AI endpoint was touched (the whole point of the canned demo).
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it.each([['teaser', AnalysisTeaser], ['landing demo', AnalysisDemo]] as const)('keeps the %s annual sample on its full fixed range', (_, Component) => {
    const { container } = render(<Component />)
    // PeekLocked intentionally removes the teaser contents from the accessibility tree.
    expect(screen.getByRole('status', { hidden: true })).toHaveTextContent('Showing 7 of 7 years')
    expect(container.querySelector('[role="group"][aria-label="Table window"]')).toBeNull()
  })
})
