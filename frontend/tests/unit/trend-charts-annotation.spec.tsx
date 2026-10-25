import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'

const tooltipContent = vi.hoisted(() => ({
  entries: [] as Array<(props: { active: boolean; label: string; payload: Array<{ dataKey: string; name: string; value: number }> }) => React.ReactNode>,
}))
beforeEach(() => { tooltipContent.entries = [] })

// recharts measures the DOM, which jsdom can't do — stub it (same pattern as trend-charts-legend).
vi.mock('recharts', async () => {
  const { createContext, useContext } = await import('react')
  type Row = Record<string, number | string | null>
  const Data = createContext<Row[]>([])
  const Chart = ({ children, data, accessibilityLayer, 'aria-label': label }: { children: React.ReactNode; data: Row[]; accessibilityLayer?: boolean; 'aria-label'?: string }) => <Data.Provider value={data}><svg data-testid="chart-layer" role={accessibilityLayer === false ? undefined : 'application'} aria-label={label} tabIndex={accessibilityLayer === false ? undefined : 0}>{children}</svg></Data.Provider>
  const project = (value: number, axis: string) => 100 - value / (axis === 'right' ? 10 : axis === 'growth' ? 2 : 1)
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
      // Recharts 3.10.1 supplies y at the value endpoint and signed height toward the baseline.
      return <g>{rows.map((row, index) => {
        const y = project(Number(row[dataKey]), 'value')
        return <g key={index}>{row[dataKey] == null ? null : shape({ x: index * 20 - 7.5, y, width: 15, height: project(0, 'value') - y, payload: row })}</g>
      })}</g>
    },
    Line: ({ dataKey, yAxisId, connectNulls, dot }: { dataKey: string; yAxisId: string; connectNulls?: boolean; dot: (props: unknown) => React.ReactNode }) => {
      const rows = useContext(Data)
      return <g data-testid="line-gap-policy" data-connect-nulls={String(connectNulls)}>{rows.map((row, index) => <g key={index}>{dot({ cx: index * 20, cy: project(Number(row[dataKey]), yAxisId), value: row[dataKey], payload: row })}</g>)}</g>
    },
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: ({ content }: { content: typeof tooltipContent.entries[number] }) => {
      tooltipContent.entries.push(content)
      return null
    },
  }
})

import TrendCharts from '@/features/analysis/components/TrendCharts'
import { ThemeContext } from '@/components/ThemeProvider'
import { chartTheme, seriesColor } from '@/components/ui'
import { groupDataNotes } from '@/features/analysis/lib/dataNotes'
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

describe('TrendCharts cash generation on one axis (spec D1, D4)', () => {
  it('names its series without an axis side: net income shares the cash flows\' scale', () => {
    render(<TrendCharts dataset={dataset} />)
    const card = screen.getByRole('heading', { name: 'Cash generation' }).closest('section')!
    expect(within(card).getByText('Net income')).toBeInTheDocument()
    expect(within(card).getByText('Operating CF')).toBeInTheDocument()
    expect(within(card).queryByText(/\((left|right)\)/)).not.toBeInTheDocument()
  })
})


describe('TrendCharts source note marks', () => {
  const passed = { version: 1 as const, method: 'reported' as const, validation: 'passed' as const, reasons: [], formula: null, inputs: [] }

  it('names each tooltip value and independent YoY note without changing its units or marking a clean period', () => {
    const revenue = series('revenue', 'Revenue', [100, 110, 120])
    revenue.points.forEach((point) => { point.provenance = passed; point.yoy = 0.125; point.yoy_provenance = passed })
    revenue.points[1].provenance = { ...passed, validation: 'needs_review', reasons: ['source_conflict'] }
    revenue.points[1].yoy_provenance = { ...passed, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] }
    render(<TrendCharts dataset={{ ...dataset, series: [revenue] }} />)
    const content = tooltipContent.entries[0]
    const payload = [
      { dataKey: 'revenue', name: 'Revenue', value: 110 },
      { dataKey: 'growth', name: 'YoY growth', value: 12.5 },
    ]
    const tooltip = render(content({ active: true, label: 'FY2023', payload }))
    const status = within(tooltip.getByRole('status'))
    // Each value prints in its axis's format: amounts at the panel's 3 significant figures, growth signed.
    expect(status.getByText('Revenue · note a').parentElement).toHaveTextContent('$110')
    expect(status.getByText('YoY growth · note b').parentElement).toHaveTextContent('+12.5%')

    tooltip.rerender(content({ active: true, label: 'FY2022', payload }))
    expect(status.getByText('Revenue')).toBeInTheDocument()
    expect(status.getByText('YoY growth')).toBeInTheDocument()
    expect(status.queryByText(/note [ab]/)).not.toBeInTheDocument()
  })

  it('marks affected bars and inherited growth independently, leaving clean points unmarked', () => {
    const revenue = series('revenue', 'Revenue', [100, 110, 120])
    revenue.points.forEach((point) => { point.provenance = passed; point.yoy = 0.1; point.yoy_provenance = passed })
    revenue.points[1].provenance = { ...passed, validation: 'needs_review', reasons: ['source_conflict'] }
    revenue.points[2].yoy_provenance = { ...passed, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] }
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [revenue] }} />)
    const bars = [...container.querySelectorAll('rect')]
    expect(bars).toHaveLength(3)
    expect(bars.every((bar) => bar.getAttribute('fill') === seriesColor(0) && !bar.hasAttribute('stroke-dasharray'))).toBe(true)
    expect(container.querySelectorAll('circle[stroke-width="2"]')).toHaveLength(1)
    expect(bars[1].parentElement).toHaveAttribute('aria-label', 'Data note a')
    expect(container.querySelector('circle')?.parentElement).toHaveAttribute('aria-label', 'Data note b')
    expect(container.querySelectorAll('text')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Review data notes a, b' })).toBeInTheDocument()
  })

  it.each([43, -43])('places bar and growth notes together at the actual %s value endpoint', (value) => {
    const revenue = series('revenue', 'Revenue', [value, null, null])
    revenue.points[0].provenance = { ...passed, validation: 'needs_review', reasons: ['source_conflict'] }
    // The independent growth scale maps twice the bar value to the same rendered y.
    revenue.points[0].yoy = value * 2 / 100
    revenue.points[0].yoy_provenance = { ...passed, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] }
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [revenue] }} />)
    const bar = container.querySelector('g[aria-label="Data note a"] rect')!
    const dot = container.querySelector('circle[stroke-width="2"]')!
    const endpoint = 100 - value
    expect(bar).toHaveAttribute('x', '-7.5')
    expect(bar).toHaveAttribute('y', String(endpoint))
    expect(bar).toHaveAttribute('width', '15')
    expect(bar).toHaveAttribute('height', String(value))
    expect(dot).toHaveAttribute('cx', '0')
    expect(dot).toHaveAttribute('cy', String(endpoint))
    const barText = bar.parentElement!.querySelector('text')!
    const growthText = dot.parentElement!.querySelector('text')!
    expect(barText.textContent).not.toBe(growthText.textContent)
    if (value < 0) {
      const labelY = Number(barText.getAttribute('y'))
      expect(Math.abs(labelY - endpoint)).toBeLessThan(Math.abs(labelY - 100))
    }
    const boxes = [barText, growthText].map((text) => {
      expect(text).toHaveAttribute('font-size', '11')
      return { x: Number(text.getAttribute('x')) - 3.5, y: Number(text.getAttribute('y')) - 11, width: 7, height: 14 }
    })
    const intersects = (a: typeof boxes[number], b: typeof boxes[number]) => Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x)
      && Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y)
    expect(intersects(boxes[0], boxes[1])).toBe(false)
    for (const box of boxes) {
      expect(intersects(box, { x: -5, y: endpoint - 5, width: 10, height: 10 })).toBe(false)
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.y).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(300)
      expect(box.y + box.height).toBeLessThanOrEqual(160)
    }
  })

  it.each(['light', 'dark'] as const)('keeps multiletter notes legible over bars with explicit SVG halo attributes in %s', (theme) => {
    const revenue = series('revenue', 'Revenue', [40, 50, 60])
    revenue.points.forEach((point) => {
      point.provenance = { ...passed, validation: 'needs_review', reasons: ['source_conflict'] }
      point.yoy = 0.5
      point.yoy_provenance = point.provenance
    })
    const data = { ...dataset, series: [revenue] }
    const grouped = groupDataNotes(data)
    const admitted = { version: 1 as const, totals: grouped.totals, notes: grouped.notes.map(note => ({ ...note, letter: 'aa', id: 'analysis-data-note-aa' })) }
    const { container } = render(<ThemeContext.Provider value={{ theme, toggleTheme: vi.fn() }}><TrendCharts dataset={{ ...data, data_notes: admitted }} /></ThemeContext.Provider>)
    const letters = [...container.querySelectorAll('g[aria-label="Data note aa"] text')]
    expect(letters).toHaveLength(6)
    for (const letter of letters) {
      expect(letter).toHaveTextContent('aa')
      expect(letter).toHaveAttribute('fill', chartTheme(theme === 'dark').label)
      expect(letter).toHaveAttribute('stroke', chartTheme(theme === 'dark').tipBg)
      expect(letter).toHaveAttribute('stroke-width', '3')
      expect(letter).toHaveAttribute('paint-order', 'stroke')
    }
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

  it('separates balance-sheet notes using each axis while keeping all plotted values fixed', () => {
    const debt = series('long_term_debt', 'Long-term debt', [43, 43, 43])
    const cash = series('cash_and_equivalents', 'Cash', [38.6, 38.6, 38.6])
    // The right axis (equity) maps 400 to y=60, between the two left-axis points (57 and 61.4).
    // Comparing raw values or projecting every value through the left axis cannot place this note.
    const equity = series('shareholders_equity', 'Equity', [400, 400, 400])
    for (const item of [debt, cash, equity]) for (const point of item.points) point.provenance = { ...passed, validation: 'needs_review', reasons: ['legacy_calculation'] }
    const { container } = render(<TrendCharts dataset={{ ...dataset, series: [debt, cash, equity] }} />)
    const marks = [...container.querySelectorAll('g[aria-label="Data note a"]')]
    expect(marks).toHaveLength(9)
    const circles = marks.map((mark) => {
      const circle = mark.querySelector('circle')!
      return { x: Number(circle.getAttribute('cx')), y: Number(circle.getAttribute('cy')) }
    })
    // Lines in the panel's order: debt (left), equity (right), cash (left).
    expect(circles.map((circle) => circle.y)).toEqual([57, 57, 57, 60, 60, 60, 61.4, 61.4, 61.4])
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
    expect(Math.abs(Number(marks[4].querySelector('text')!.getAttribute('y')) - circles[4].y)).toBeLessThan(32)
  })
})

describe('TrendCharts keyboard viewport', () => {
  it('keeps named chart-value navigation beside the conditional scrolling stop and cleans up on unmount', () => {
    let width = 300
    const callbacks: Array<() => void> = []
    const disconnect = vi.fn()
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { callbacks.push(callback) }
      observe() {}
      disconnect = disconnect
    })
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => width)
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(500)
    try {
      const { container, unmount } = render(<TrendCharts dataset={{ ...dataset, series: [series('revenue', 'Revenue', [30, 40, 50]), ...dataset.series] }} />)
      const viewports = [...container.querySelectorAll('[data-analysis-chart-scroll]')]
      expect(viewports).toHaveLength(3)
      for (const viewport of viewports) {
        expect(viewport).toHaveAttribute('tabindex', '0')
        expect(viewport).toHaveAttribute('role', 'region')
        expect(viewport).toHaveAccessibleName(/chart\. Scroll horizontally to view all periods\./)
        expect(viewport.querySelectorAll('[tabindex]')).toHaveLength(1)
        expect(viewport.querySelector('[tabindex]')).toHaveAttribute('tabindex', '0')
        expect(viewport.querySelector('[role=application]')).toHaveAccessibleName(/chart values\. Use Left and Right arrows to inspect periods\./)
      }
      width = 500
      act(() => callbacks.forEach(callback => callback()))
      for (const viewport of viewports) {
        expect(viewport).not.toHaveAttribute('tabindex')
        expect(viewport).not.toHaveAttribute('role')
        expect(viewport).not.toHaveAttribute('aria-label')
        expect(viewport.querySelector('[role=application]')).toHaveAttribute('tabindex', '0')
      }
      width = 280
      act(() => callbacks.forEach(callback => callback()))
      expect(screen.getAllByRole('region')).toHaveLength(3)
      unmount()
      expect(disconnect).toHaveBeenCalledTimes(3)
    } finally { vi.restoreAllMocks(); vi.unstubAllGlobals() }
  })
})
