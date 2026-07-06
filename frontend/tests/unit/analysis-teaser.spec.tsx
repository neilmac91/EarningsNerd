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

import AnalysisTeaser from '@/features/analysis/components/AnalysisTeaser'

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
    expect(screen.getByText(/upgrade to run it for MSFT/)).toBeInTheDocument()
    // …and NO backend/AI endpoint was touched (the whole point of the canned demo).
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})
