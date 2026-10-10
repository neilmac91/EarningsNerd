import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do — stub it (same pattern as trend-charts-legend).
vi.mock('recharts', async () => {
  const { createContext, useContext } = await import('react')
  type Row = Record<string, number | string | null>
  const Data = createContext<Row[]>([])
  const Chart = ({ children, data }: { children: React.ReactNode; data: Row[] }) => <Data.Provider value={data}><svg>{children}</svg></Data.Provider>
  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ComposedChart: Chart,
    LineChart: Chart,
    Rectangle: (props: React.SVGProps<SVGRectElement>) => <rect {...props} />,
    Bar: ({ dataKey, shape }: { dataKey: string; shape: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g>{rows.map((row, index) => <g key={index}>{row[dataKey] == null ? null : shape({ x: index * 20, y: 50, width: 15, height: 60, payload: row })}</g>)}</g>
    },
    Line: ({ dataKey, connectNulls, dot }: { dataKey: string; connectNulls?: boolean; dot: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g data-testid="line-gap-policy" data-connect-nulls={String(connectNulls)}>{rows.map((row, index) => <g key={index}>{dot({ cx: index * 20, cy: 50, value: row[dataKey], payload: row })}</g>)}</g>
    },
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
  }
})

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


describe('TrendCharts source note marks', () => {
  const passed = { version: 1 as const, method: 'reported' as const, validation: 'passed' as const, reasons: [], formula: null, inputs: [] }

  it('marks affected bars and inherited growth independently, leaving clean points unmarked', () => {
    const revenue = series('revenue', 'Revenue', [100, 110, 120])
    revenue.points.forEach((point) => { point.provenance = passed; point.yoy = 0.1; point.yoy_provenance = passed })
    revenue.points[1].provenance = { ...passed, validation: 'needs_review', reasons: ['source_conflict'] }
    revenue.points[2].yoy_provenance = { ...passed, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] }
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [revenue] }} />)
    expect(container.querySelectorAll('rect[stroke-dasharray="4 3"]')).toHaveLength(1)
    expect(container.querySelectorAll('circle[stroke-width="2"]')).toHaveLength(1)
    expect(container.querySelector('rect[stroke-dasharray]')?.parentElement).toHaveAttribute('aria-label', 'Data note a')
    expect(container.querySelector('circle')?.parentElement).toHaveAttribute('aria-label', 'Data note b')
    expect(container.querySelectorAll('text')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Review data notes a, b' })).toBeInTheDocument()
  })

  it('never invents a plotted marker for a missing figure', () => {
    const cash = series('operating_cash_flow', 'Operating CF', [100, null, 120])
    cash.points.forEach((point) => { point.provenance = passed })
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [cash] }} />)
    expect(container.querySelectorAll('circle, rect, text')).toHaveLength(0)
    expect(screen.getByText('Operating CF: unavailable for FY2023.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review data notes a' })).toBeInTheDocument()
  })
})
