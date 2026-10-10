import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do — stub it (same pattern as trend-charts-legend).
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: (props: { connectNulls?: boolean }) => <span data-testid="line-gap-policy" data-connect-nulls={String(props.connectNulls)} />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))

import TrendCharts from '@/features/analysis/components/TrendCharts'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'

const period = (key: string, year: number) => ({
  key,
  fiscal_year: year,
  fiscal_period: 'FY' as const,
  period_end: `${year}-12-31`,
})

const series = (concept: string, label: string, values: (number | null)[], extra: Partial<AnalysisSeries> = {}): AnalysisSeries => ({
  concept,
  label,
  unit: 'USD',
  percent: false,
  cagr: null,
  points: ['FY2022', 'FY2023', 'FY2024']
    .map((p, i) => (values[i] == null ? null : { period: p, value: values[i] as number }))
    .filter((x): x is { period: string; value: number } => x !== null),
  ...extra,
})

const dataset: AnalysisDataset = {
  ticker: 'TST',
  company_name: 'Test Co',
  mode: 'annual',
  period_key: 'FY2022..FY2024',
  periods: [period('FY2022', 2022), period('FY2023', 2023), period('FY2024', 2024)],
  series: [
    // Cash generation panel — net_income present so it takes the right axis.
    series('operating_cash_flow', 'Operating CF', [10, 12, 14]),
    series('free_cash_flow', 'Free cash flow', [5, 6, 7]),
    series('net_income', 'Net income', [8, 9, 10]),
    // Balance sheet panel — Cash stops 2 periods early (reported only in FY2022).
    series('long_term_debt', 'Long-term debt', [40, 35, 30], { tone: 'inverted' }),
    series('shareholders_equity', 'Equity', [900, 1000, 1100]),
    series('cash_and_equivalents', 'Cash', [50, null, null]),
  ],
  inflections: [],
}

describe('TrendCharts missing-data annotation (P1-8)', () => {
  it('names unavailable periods without claiming the company did not report them', () => {
    render(<TrendCharts dataset={dataset} />)
    // Cash is reported only through FY2022; connectNulls can't bridge the trailing gap, so the
    // line just stops — the footnote explains why.
    expect(screen.getByText(/Cash: unavailable for FY2023, FY2024/)).toBeInTheDocument()
    expect(screen.getAllByTestId('line-gap-policy').every((line) => line.getAttribute('data-connect-nulls') === 'false')).toBe(true)
  })

  it('does not annotate a series that spans the full window', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.queryByText(/Operating CF: unavailable/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Equity: unavailable/)).not.toBeInTheDocument()
  })
})

describe('TrendCharts cash-generation dual axis (P1-8)', () => {
  it('marks net income (right) and the cash-flow series (left) symmetrically', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.getByText('Net income (right)')).toBeInTheDocument()
    // The left-axis cash-flow series are now positively bound with "(left)" too (symmetric legend).
    expect(screen.getByText('Operating CF (left)')).toBeInTheDocument()
    expect(screen.getByText('Free cash flow (left)')).toBeInTheDocument()
  })
})
