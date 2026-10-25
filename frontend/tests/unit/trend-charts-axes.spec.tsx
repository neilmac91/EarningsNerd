import { readFileSync } from 'node:fs'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from '@testing-library/react'

/**
 * Today's Recharts panels take their value axes from the chart engine (step 2 of the migration plan): every axis prints the engine's ticks,
 * domain and labels, so the cards already read as the engine's plans (spec A1, A2) on the 19 real filed datasets the
 * engine's own checks run on. The cash panel has one axis (D1, D4); amounts carry the filer's currency; a percent
 * axis holds every value, because Recharts cannot print a clipped one at the plot edge.
 */
const tooltips = vi.hoisted(() => ({ contents: [] as Array<(props: unknown) => React.ReactElement | null> }))
beforeEach(() => { tooltips.contents = [] })

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <svg>{children}</svg>,
  LineChart: ({ children }: { children: React.ReactNode }) => <svg>{children}</svg>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  // Each axis prints its props, labels formatted the way Recharts calls tickFormatter.
  YAxis: ({ yAxisId, ticks, domain, width, interval, tickFormatter, tick, tickMargin }: {
    yAxisId: string; ticks?: number[]; domain?: [number, number]; width: number; interval?: number; tickFormatter: (value: number, index: number) => string
    tick: { fontSize: number }; tickMargin: number
  }) => (
    <g data-y-axis={yAxisId} data-ticks={JSON.stringify(ticks ?? null)} data-domain={JSON.stringify(domain ?? null)}
      data-labels={JSON.stringify((ticks ?? []).map((value, index) => tickFormatter(value, index)))} data-width={width} data-interval={interval}
      data-font-size={tick.fontSize} data-tick-margin={tickMargin} />
  ),
  CartesianGrid: () => null,
  Tooltip: ({ content }: { content: (props: unknown) => React.ReactElement | null }) => {
    tooltips.contents.push(content)
    return null
  },
}))

import TrendCharts from '@/features/analysis/components/TrendCharts'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { CHART_IDS, MIXED_CURRENCY, buildChartModel, type ChartId, type ModelPanel } from '@/features/analysis/lib/charts/model'
import { resolveDataNotes, type DataNote } from '@/features/analysis/lib/dataNotes'
import { comparisonLocations, selectHeadlineFigures, topLineConcept } from '@/features/analysis/lib/reportPresentation'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { case: string; dataset: AnalysisDataset }>
}
const DATASETS = Object.keys(FIXTURE.datasets)
const dataset = (name: string) => structuredClone(FIXTURE.datasets[name].dataset)

interface DrawnAxis { ticks: number[]; domain: [number, number]; labels: string[]; width: number; interval: string | null; fontSize: number; tickMargin: number }

const chartOf = (title: string): ChartId =>
  title.endsWith('& growth') ? 'topline' : title === 'Margins' ? 'margins' : title === 'Cash generation' ? 'cash' : 'balance'

/** The value axes each drawn panel prints, by chart and axis id. */
function drawnAxes(ds: AnalysisDataset): Partial<Record<ChartId, Record<string, DrawnAxis>>> {
  const { container, unmount } = render(<TrendCharts dataset={ds} />)
  const charts: Partial<Record<ChartId, Record<string, DrawnAxis>>> = {}
  for (const plot of container.querySelectorAll<HTMLElement>('[data-analysis-chart]')) {
    const axes: Record<string, DrawnAxis> = {}
    for (const axis of plot.querySelectorAll<SVGGElement>('[data-y-axis]')) {
      axes[axis.dataset.yAxis!] = {
        ticks: JSON.parse(axis.dataset.ticks!), domain: JSON.parse(axis.dataset.domain!), labels: JSON.parse(axis.dataset.labels!),
        width: Number(axis.dataset.width), interval: axis.dataset.interval ?? null,
        fontSize: Number(axis.dataset.fontSize), tickMargin: Number(axis.dataset.tickMargin),
      }
    }
    charts[chartOf(plot.dataset.analysisChart!)] = axes
  }
  unmount()
  return charts
}

/** The room a y tick label takes as Recharts draws it: its glyphs at the tick's font size and Geist Mono's 0.6 em
 *  advance, set in from the plot by the tick margin and Recharts' 6 px tick length, which it keeps with the line off. */
const labelRoom = (axis: DrawnAxis, label: string) => [...label].length * axis.fontSize * 0.6 + axis.tickMargin + 6
const engineAxis = (panel: ModelPanel) => ({ ticks: panel.axis.ticks, domain: panel.axis.domain, labels: panel.axis.ticks.map(panel.axis.format.tick) })
/** A drawn label prints a no-break space where the engine's has a space (see the one-line test). */
const sameAxis = ({ ticks, domain, labels }: DrawnAxis) => ({ ticks, domain, labels: labels.map((label) => label.replace(/\u00a0/g, ' ')) })
const offscale = (panel: ModelPanel) => panel.marks.some((mark) => mark.points.some((point) => point.offscale))
const valuesOf = (panel: ModelPanel) => panel.marks.flatMap((mark) => mark.points.flatMap((point) => (point.value == null ? [] : [point.value])))

describe.each(DATASETS)('%s: the drawn axes are the engine’s', (name) => {
  const drawn = drawnAxes(dataset(name))
  const models = Object.fromEntries(CHART_IDS.map((chart) => [chart, buildChartModel(chart, dataset(name))]))

  it('every axis prints all of its ticks and has room for its widest label', () => {
    for (const axes of Object.values(drawn)) for (const axis of Object.values(axes!)) {
      expect(axis.interval).toBe('0')
      for (const label of axis.labels) expect(axis.width, label).toBeGreaterThanOrEqual(labelRoom(axis, label))
    }
  })

  it('a chart the engine draws is drawn, and one it cannot draw is not', () => {
    for (const chart of CHART_IDS) expect(Boolean(drawn[chart]), chart).toBe(models[chart].panels.length > 0)
  })

  it('the amount axes carry the engine’s ticks, domain and labels', () => {
    const { topline, cash, balance } = models
    if (drawn.topline) expect(sameAxis(drawn.topline.value)).toEqual(engineAxis(topline.panels[0]))
    if (drawn.cash) {
      expect(Object.keys(drawn.cash), 'cash generation has one axis').toEqual(['left'])
      expect(sameAxis(drawn.cash.left)).toEqual(engineAxis(cash.panels[0]))
    }
    if (drawn.balance) {
      const [debtcash, equity] = ['debtcash', 'equity'].map((id) => balance.panels.find((panel) => panel.id === id))
      expect(sameAxis(drawn.balance.left)).toEqual(engineAxis((debtcash ?? equity)!))
      if (debtcash && equity) expect(sameAxis(drawn.balance.right)).toEqual(engineAxis(equity))
      else expect(drawn.balance.right).toBeUndefined()
    }
  })

  it('a percent axis is the engine’s, or holds every value the engine clipped', () => {
    const percent: Array<[DrawnAxis | undefined, ModelPanel | undefined]> = [
      [drawn.topline?.growth, models.topline.panels[1]], [drawn.margins?.left, models.margins.panels[0]],
    ]
    for (const [axis, panel] of percent) {
      if (!axis || !panel) continue
      if (!offscale(panel)) {
        expect(sameAxis(axis)).toEqual(engineAxis(panel))
        continue
      }
      const values = valuesOf(panel)
      expect(axis.domain[0]).toBeLessThanOrEqual(Math.min(0, ...values))
      expect(axis.domain[1]).toBeGreaterThanOrEqual(Math.max(0, ...values))
      expect(axis.domain[1] - axis.domain[0]).toBeGreaterThan(panel.axis.domain[1] - panel.axis.domain[0])
    }
  })
})

describe('the cases step 2 changes', () => {
  it('REGN cash generation: one axis, so FY2025 free cash flow ($4.08B) reads below net income ($4.50B)', () => {
    const { cash } = drawnAxes(dataset('REGN_annual'))
    expect(Object.keys(cash!)).toEqual(['left'])
    expect(cash!.left.labels).toEqual(['$0', '$2B', '$4B', '$6B', '$8B', '$10B'])
  })

  it('LCID margins: the axis reaches −18,093% rather than clipping a value Recharts would draw past the edge', () => {
    const { margins } = drawnAxes(dataset('LCID_annual'))
    expect(margins!.left.domain[0]).toBeLessThanOrEqual(-18093)
    expect(margins!.left.labels.at(-1)).toBe('0%')
  })

  // Equity's cap (4 intervals) and debt and cash's (6) give these two different ticks.
  it.each(['AAPL_annual', 'BYND_annual'])('%s: a balance sheet with equity alone draws it on the left, at equity’s own cap', (name) => {
    const ds = dataset(name)
    ds.series = ds.series.filter((series) => series.concept === 'shareholders_equity')
    const { balance } = drawnAxes(ds)
    expect(Object.keys(balance!)).toEqual(['left'])
    expect(sameAxis(balance!.left)).toEqual(engineAxis(buildChartModel('balance', ds).panels[0]))
  })

  it('a yen filer’s axes read in yen, never a default dollar sign', () => {
    const ds = dataset('REGN_annual')
    for (const series of ds.series) if (!series.percent) {
      series.unit = 'JPY'
      for (const point of series.points) point.unit = 'JPY'
    }
    const drawn = drawnAxes(ds)
    expect(drawn.topline!.value.labels).toEqual(['¥0', '¥5B', '¥10B', '¥15B', '¥20B'])
    for (const axis of [drawn.cash!.left, drawn.balance!.left, drawn.balance!.right]) expect(axis.labels.slice(1).every((label) => label.startsWith('¥'))).toBe(true)
  })

  it('a code-prefixed currency widens its axes past their floors to hold every label', () => {
    const ds = dataset('BYND_annual')
    for (const series of ds.series) if (!series.percent) {
      series.unit = 'CHF'
      for (const point of series.points) point.unit = 'CHF'
    }
    const axes = Object.values(drawnAxes(ds)).flatMap((chart) => Object.values(chart!))
    expect(axes.some((axis) => axis.width > 64 && axis.labels.some((label) => label.startsWith('−CHF')))).toBe(true)
    for (const axis of axes) for (const label of axis.labels) expect(axis.width, label).toBeGreaterThanOrEqual(labelRoom(axis, label))
  })

  it('a tick label has no space Recharts could break it at', () => {
    const ds = dataset('BYND_annual')
    for (const series of ds.series) if (!series.percent) {
      series.unit = 'CHF'
      for (const point of series.points) point.unit = 'CHF'
    }
    const labels = Object.values(drawnAxes(ds)).flatMap((chart) => Object.values(chart!)).flatMap((axis) => axis.labels)
    expect(labels).toContain('CHF\u00a00')
    expect(labels.filter((label) => /[ \f\n\r\t\v\u2028\u2029]/.test(label))).toEqual([])
  })

  it('amounts in two currencies say so instead of drawing one scale', () => {
    const ds = dataset('REGN_annual')
    ds.series.find((series) => series.concept === 'net_income')!.points[3].unit = 'EUR'
    const { container } = render(<TrendCharts dataset={ds} />)
    const cash = [...container.querySelectorAll('section')].find((section) => section.querySelector('h2')?.textContent === 'Cash generation')!
    expect(cash.textContent).toContain(MIXED_CURRENCY)
    expect(cash.querySelector('[data-analysis-chart], [data-y-axis]')).toBeNull()
    expect(container.querySelector('[data-analysis-chart="Revenue & growth"]')).not.toBeNull()
  })

  it('a tooltip prints each series in its own axis’s format: equity on the right axis, margins at 1 dp', () => {
    const ds = dataset('REGN_annual')
    ds.series = ds.series.filter((series) => ['long_term_debt', 'shareholders_equity'].includes(series.concept))
    render(<TrendCharts dataset={ds} />)
    const balance = render(tooltips.contents.at(-1)!({
      active: true, label: 'FY2025', payload: [
        { dataKey: 'long_term_debt', name: 'Long-term debt', value: 1_983_000_000, color: '#000' },
        { dataKey: 'shareholders_equity', name: 'Equity', value: 31_365_400_000, color: '#000' },
      ],
    })!)
    expect(balance.container.textContent).toContain('$1.98B')
    expect(balance.container.textContent).toContain('$31.4B')

    const margins = dataset('REGN_annual')
    margins.series = margins.series.filter((series) => series.concept.endsWith('_margin'))
    render(<TrendCharts dataset={margins} />)
    const tip = render(tooltips.contents.at(-1)!({ active: true, label: 'FY2025', payload: [{ dataKey: 'net_margin', name: 'Net', value: 31.06, color: '#000' }] })!)
    expect(tip.container.textContent).toContain('31.1%')
  })
})

describe('the first chart and the notes agree on what it draws', () => {
  const yoyNote = (concept: string, period: string) => ({ comparisons: [{ concept, period, basis: 'yoy' }] }) as unknown as DataNote

  it('a note names the growth chart for a comparison it plots, and not once the top line is in two currencies', () => {
    const ds = dataset('REGN_annual')
    expect(comparisonLocations(ds, ds.periods, resolveDataNotes(ds))(yoyNote('revenue', 'FY2024'))[0].chart).toBe(1)
    ds.series.find((series) => series.concept === 'revenue')!.points[3].unit = 'EUR'
    expect(comparisonLocations(ds, ds.periods, resolveDataNotes(ds))(yoyNote('revenue', 'FY2024'))[0].chart).toBe(0)
    const { container } = render(<TrendCharts dataset={ds} />)
    expect(container.querySelector('[data-analysis-chart="Revenue & growth"]')).toBeNull()
    expect(container.textContent).toContain(MIXED_CURRENCY)
  })

  it('with no top line in the window, no first chart is drawn, as the engine draws none', () => {
    const ds = dataset('LOVE_annual')
    ds.series = ds.series.filter((series) => series.concept !== 'net_interest_income')
    ds.series.find((series) => series.concept === 'revenue')!.points = []
    expect(drawnAxes(ds).topline).toBeUndefined()
    expect(buildChartModel('topline', ds).panels).toEqual([])
  })
})

describe('the top line the KPI strip, the notes and the first chart share (D16)', () => {
  it('an insurer’s is premiums earned, a bank’s net interest income', () => {
    expect(topLineConcept(dataset('PGR_quarterly'))).toBe('premiums_earned')
    expect(selectHeadlineFigures(dataset('PGR_quarterly'))[0].series.concept).toBe('premiums_earned')
    expect(topLineConcept(dataset('JPM_annual'))).toBe('net_interest_income')
    expect(topLineConcept(dataset('LOVE_annual'))).toBe('revenue')
    expect(topLineConcept(dataset('O_annual'))).toBe('revenue')
  })

  it('revenue with no value in the window gives way to the next top line', () => {
    const ds = dataset('LOVE_annual')
    ds.series.find((series) => series.concept === 'revenue')!.points = []
    expect(topLineConcept(ds)).toBe('net_interest_income')
    expect(selectHeadlineFigures(ds)[0].series.concept).toBe('net_interest_income')
  })
})
