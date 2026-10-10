import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do — stub it (same pattern as trend-charts-legend).
vi.mock('recharts', async () => {
  const { createContext, useContext } = await import('react')
  type Row = Record<string, number | string | null>
  const Data = createContext<Row[]>([])
  const Chart = ({ children, data }: { children: React.ReactNode; data: Row[] }) => <Data.Provider value={data}><svg>{children}</svg></Data.Provider>
  const project = (value: number, axis: string) => 100 - value / (axis === 'right' ? 10 : 1)
  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ComposedChart: Chart,
    LineChart: Chart,
    Rectangle: (props: React.SVGProps<SVGRectElement>) => <rect {...props} />,
    usePlotArea: () => ({ x: 0, y: 0, width: 300, height: 160 }),
    useXAxisScale: () => {
      const rows = useContext(Data)
      return (period: string) => rows.findIndex((row) => row.period === period) * 20
    },
    useYAxisScale: (axis: string) => (value: number) => project(value, axis),
    Bar: ({ dataKey, shape }: { dataKey: string; shape: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g>{rows.map((row, index) => <g key={index}>{row[dataKey] == null ? null : shape({ x: index * 20, y: 50, width: 15, height: 60, payload: row })}</g>)}</g>
    },
    Line: ({ dataKey, yAxisId, connectNulls, dot }: { dataKey: string; yAxisId: string; connectNulls?: boolean; dot: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g data-testid="line-gap-policy" data-connect-nulls={String(connectNulls)}>{rows.map((row, index) => <g key={index}>{dot({ cx: index * 20, cy: project(Number(row[dataKey]), yAxisId), value: row[dataKey], payload: row })}</g>)}</g>
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

  it('moves close margin letters apart while retaining their true plotted circle positions', () => {
    const operating = series('operating_margin', 'Operating margin', [43, 43, 43])
    const net = series('net_margin', 'Net margin', [38.6, 38.6, 38.6])
    for (const item of [operating, net]) for (const point of item.points) point.provenance = { ...passed, validation: 'needs_review', reasons: ['legacy_calculation'] }
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [operating, net] }} />)
    const marks = [...container.querySelectorAll('g[aria-label="Data note a"]')]
    expect(marks).toHaveLength(6)
    const upper = marks[1]
    const lower = marks[4]
    expect(upper.querySelector('circle')).toHaveAttribute('cy', '57')
    expect(lower.querySelector('circle')).toHaveAttribute('cy', '61.4')
    expect(Number(upper.querySelector('text')!.getAttribute('y'))).toBeLessThan(57)
    expect(Number(lower.querySelector('text')!.getAttribute('y'))).toBeGreaterThan(61.4)
    expect(marks.every((mark) => mark.querySelector('text')!.getAttribute('font-size') === '11')).toBe(true)
  })

  it('separates cash-flow notes using each axis while keeping all plotted values fixed', () => {
    const operating = series('operating_cash_flow', 'Operating CF', [43, 43, 43])
    const cash = series('free_cash_flow', 'Free cash flow', [38.6, 38.6, 38.6])
    // The right axis maps 400 to y=60, between the two left-axis points (57 and 61.4).
    // Comparing raw values or projecting every value through the left axis cannot place this note.
    const income = series('net_income', 'Net income', [400, 400, 400])
    for (const item of [operating, cash, income]) for (const point of item.points) point.provenance = { ...passed, validation: 'needs_review', reasons: ['legacy_calculation'] }
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [operating, cash, income] }} />)
    const marks = [...container.querySelectorAll('g[aria-label="Data note a"]')]
    expect(marks).toHaveLength(9)
    const circles = marks.map((mark) => {
      const circle = mark.querySelector('circle')!
      return { x: Number(circle.getAttribute('cx')), y: Number(circle.getAttribute('cy')) }
    })
    expect(circles.map((circle) => circle.y)).toEqual([57, 57, 57, 61.4, 61.4, 61.4, 60, 60, 60])
    const letters = marks.map((mark) => {
      const text = mark.querySelector('text')!
      expect(text).toHaveAttribute('font-size', '11')
      return { x: Number(text.getAttribute('x')) - 3.5, y: Number(text.getAttribute('y')) - 11, width: 7, height: 14 }
    })
    const intersects = (a: typeof letters[number], b: typeof letters[number]) => Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x)
      && Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y)
    for (const [index, letter] of letters.entries()) {
      for (const circle of circles) expect(intersects(letter, { x: circle.x - 5, y: circle.y - 5, width: 10, height: 10 })).toBe(false)
      for (const other of letters.slice(index + 1)) expect(intersects(letter, other)).toBe(false)
    }
    // The middle right-axis note remains near its actual point, not clamped from the wrong scale.
    expect(Math.abs(Number(marks[7].querySelector('text')!.getAttribute('y')) - circles[7].y)).toBeLessThan(32)
  })
})
