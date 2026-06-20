import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// recharts measures the DOM, which jsdom can't do — stub it for deterministic rendering.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))

const getFundamentals = vi.fn()
vi.mock('@/features/fundamentals/api/fundamentals-api', () => ({
  getFundamentals: (...args: unknown[]) => getFundamentals(...args),
}))

import FundamentalsTrendChart from '@/features/fundamentals/components/FundamentalsTrendChart'

function renderChart(ticker = 'AAPL') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <FundamentalsTrendChart ticker={ticker} />
    </QueryClientProvider>,
  )
}

const point = (fy: number, value: number, unit: string, reconciled = true) => ({
  period_end: `${fy}-12-31`,
  fiscal_year: fy,
  fiscal_period: 'FY',
  value,
  unit,
  form: '10-K',
  accession: `acc-${fy}`,
  reconciled,
})

const RESP = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  concepts: [
    { concept: 'revenue', unit: 'USD', points: [point(2022, 394328000000, 'USD'), point(2023, 383285000000, 'USD')] },
    { concept: 'net_margin', unit: 'pure', points: [point(2023, 25.3, 'pure')] },
    { concept: 'some_unfeatured_concept', unit: 'USD', points: [point(2023, 1, 'USD')] },
  ],
}

describe('FundamentalsTrendChart', () => {
  beforeEach(() => getFundamentals.mockReset())

  it('shows only featured concepts present in the response, defaulting to the first', async () => {
    getFundamentals.mockResolvedValue(RESP)
    renderChart()

    // Wait on a data-driven button (the heading also shows during loading).
    const revenueBtn = await screen.findByRole('button', { name: 'Revenue' })
    expect(revenueBtn).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Financial Trends')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Net Margin' })).toBeInTheDocument()
    expect(screen.queryByText('some_unfeatured_concept')).not.toBeInTheDocument()
    expect(screen.getByTestId('fundamentals-chart')).toBeInTheDocument()
    // Clean data → no honesty badge.
    expect(screen.queryByText('Unverified')).not.toBeInTheDocument()
  })

  it('shows the Unverified badge when the active series has a flagged value', async () => {
    getFundamentals.mockResolvedValue({
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      concepts: [
        { concept: 'revenue', unit: 'USD', points: [point(2022, 100, 'USD'), point(2023, 0, 'USD', false)] },
      ],
    })
    renderChart()

    expect(await screen.findByText('Unverified')).toBeInTheDocument()
  })

  it('switches the active metric on click', async () => {
    getFundamentals.mockResolvedValue(RESP)
    renderChart()

    const netMargin = await screen.findByRole('button', { name: 'Net Margin' })
    fireEvent.click(netMargin)

    expect(netMargin).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Revenue' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders nothing once loaded for a company with no facts', async () => {
    getFundamentals.mockResolvedValue({ ticker: 'AAPL', company_name: 'Apple Inc.', concepts: [] })
    renderChart()

    await waitFor(() => expect(screen.queryByText('Financial Trends')).not.toBeInTheDocument())
  })
})
