import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports).
const h = vi.hoisted(() => ({
  enableMarketMovers: false,
  fetchTrendingInitial: vi.fn(async () => null),
}))

// Stub factory for homepage children — must be hoisted too, since the vi.mock factories that
// call it are hoisted above this file's top-level statements.
const stub = vi.hoisted(
  () => (testid: string) => ({ default: () => <div data-testid={testid} /> })
)

vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_MARKET_MOVERS() {
    return h.enableMarketMovers
  },
  exampleFilingHref: (entry: string) => `/company/AAPL?entry=${entry}`,
  EXAMPLE_FILING_ID: undefined,
}))

vi.mock('@/lib/serverApi', () => ({
  fetchExampleData: vi.fn(async () => null),
  fetchNotableFilings: vi.fn(async () => null),
  fetchTrendingInitial: h.fetchTrendingInitial,
  fetchReportingThisWeek: vi.fn(async () => null),
}))

// Stub every homepage child so the page renders without client-only machinery; the two under
// test get testids.
vi.mock('@/features/companies/components/CompanySearch', () => stub('company-search'))
vi.mock('@/features/marketing/components/QuickAccessBar', () => stub('quick-access'))
vi.mock('@/features/filings/components/NotableFilings', () => stub('notable-filings'))
vi.mock('@/features/companies/components/TrendingTickers', () => stub('market-movers'))
vi.mock('@/features/marketing/components/HeroExample', () => stub('hero-example'))
vi.mock('@/features/marketing/components/ExampleSummaryCard', () => stub('example-summary'))
vi.mock('@/features/calendar/components/ReportingThisWeek', () => stub('reporting-this-week'))
vi.mock('@/features/marketing/components/SocialProofStrip', () => stub('social-proof'))
vi.mock('@/features/marketing/components/HowItWorks', () => stub('how-it-works'))
vi.mock('@/features/marketing/components/FeatureShowcase', () => stub('feature-showcase'))
vi.mock('@/features/marketing/components/AccuracySection', () => stub('accuracy'))
vi.mock('@/features/marketing/components/CtaBanner', () => stub('cta-banner'))
vi.mock('@/features/marketing/components/ExampleCtaLink', () => ({
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

import Home from '@/app/page'

describe('Market Movers gating (NEXT_PUBLIC_ENABLE_MARKET_MOVERS)', () => {
  beforeEach(() => {
    h.fetchTrendingInitial.mockClear()
  })

  it('flag off (default): section absent AND its prefetch skipped', async () => {
    h.enableMarketMovers = false
    render(await Home())

    expect(screen.queryByTestId('market-movers')).not.toBeInTheDocument()
    expect(h.fetchTrendingInitial).not.toHaveBeenCalled()
    // The replacement section mounts unconditionally (it self-omits via its own data contract).
    expect(screen.getByTestId('notable-filings')).toBeInTheDocument()
  })

  it('flag on: section renders and the prefetch runs', async () => {
    h.enableMarketMovers = true
    render(await Home())

    expect(screen.getByTestId('market-movers')).toBeInTheDocument()
    expect(h.fetchTrendingInitial).toHaveBeenCalledTimes(1)
  })
})
