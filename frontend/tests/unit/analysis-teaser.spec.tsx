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
// More than six periods makes the sample contract observable at both real call sites. The run ends at
// FY2025, so the added seventh year is the one after it.
vi.mock('@/features/analysis/demo/demo-analysis.json', async importOriginal => {
  const original = await importOriginal<{ default: typeof import('@/features/analysis/demo/demo-analysis.json') }>()
  return { default: { ...original.default, dataset: { ...original.default.dataset,
    periods: [...original.default.dataset.periods, { key: 'FY2026', fiscal_year: 2026, fiscal_period: 'FY', period_end: '2026-09-26' }],
  } } }
})

import demo from '@/features/analysis/demo/demo-analysis.json'
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
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    // …the sample is honestly labelled, with the company and window of the run it renders (read from the
    // payload, so the line cannot fall behind a regeneration), and personalized…
    const { company_name, ticker, periods } = demo.dataset
    expect(screen.getByText(`Sample: ${company_name} (${ticker}), ${periods[0].key}–${periods[periods.length - 1].key}. Upgrade to run it for MSFT.`)).toBeInTheDocument()
    expect(company_name).toBe('Apple Inc.')
    // …and NO backend/AI endpoint was touched (the whole point of the canned demo).
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('makes the locked preview inert, so Tab reaches Upgrade to Pro without crossing the blurred controls', () => {
    render(<AnalysisTeaser forTicker="MSFT" />)
    const preview = screen.getByRole('status', { hidden: true }).closest('[aria-hidden="true"]')
    // Each of the run's values is a button, a Tab stop unless the preview is inert.
    expect(preview?.querySelectorAll('button').length).toBeGreaterThan(0)
    expect(preview).toHaveAttribute('inert')
    // Testing Library reads no inert, so the upgrade button is held outside every inert subtree here.
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' }).closest('[inert]')).toBeNull()
  })

  it.each([['teaser', AnalysisTeaser], ['landing demo', AnalysisDemo]] as const)('keeps the %s annual sample on its full fixed range', (_, Component) => {
    const { container } = render(<Component />)
    // PeekLocked intentionally removes the teaser contents from the accessibility tree.
    expect(screen.getByRole('status', { hidden: true })).toHaveTextContent('Showing 7 of 7 years')
    expect(container.querySelector('[role="group"][aria-label="Table window"]')).toBeNull()
  })
})
