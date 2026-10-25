/* =============================================================================
   trend-charts-v2.spec.tsx — the spec renderer (CHARTS_V2, E192) draws the engine's plan
   -----------------------------------------------------------------------------
   TrendChartSvg only paints what features/analysis/lib/charts plans, so these checks hold the DOM to the plan on every
   fixture dataset and chart: the spec's DOM checks that need no layout engine (docs/design/analysis-trend-charts-spec-
   2026-10.md §6: D4, D5, D7, D11, D12, D14), every printed string, and literal paint the PNG export can serialise. The
   card around it: the legend, footnotes, a chart that does not apply, the residual sentence, the export's header, the
   dark tokens, the expanded view, and the flag switch in TrendCharts. Text boxes, collisions and the font (D1, D2,
   D8) need a browser: tests/e2e/charts-v2.spec.ts.
============================================================================= */
import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { renderToString } from 'react-dom/server'

const flags = vi.hoisted(() => ({ v2: true }))
vi.mock('@/lib/featureFlags', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/featureFlags')>()
  return { ...actual, get CHARTS_V2() { return flags.v2 } }
})
// The Recharts grid is the flag-off branch only; jsdom cannot measure it (same stub as trend-charts-legend.spec.tsx).
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-recharts>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Rectangle: () => null,
  usePlotArea: () => null,
  useXAxisScale: () => null,
  useYAxisScale: () => null,
}))
vi.mock('@/features/analysis/lib/chartExport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/analysis/lib/chartExport')>()
  return { ...actual, exportPanelPng: vi.fn().mockResolvedValue(true) }
})
vi.mock('@/lib/analytics', () => ({ default: { exportGenerated: vi.fn() } }))
vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: { ...actual.toast, error: vi.fn() } }
})

import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import TrendCharts from '@/features/analysis/components/TrendCharts'
import TrendChartsV2 from '@/features/analysis/components/TrendChartsV2'
import { ThemeContext } from '@/components/ThemeProvider'
import { exportPanelPng } from '@/features/analysis/lib/chartExport'
import { CARD_HEIGHT, layoutChart, noteGlyphs, VALUES_DONT_FIT, type ChartLayout } from '@/features/analysis/lib/charts/layout'
import { buildChartModel, CHART_IDS, type ChartModel, type ChartView } from '@/features/analysis/lib/charts/model'
import { CHART_TOKENS, type ChartTokens } from '@/features/analysis/lib/charts/theme'
import { resolveDataNotes } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import analytics from '@/lib/analytics'
import { toast } from 'sonner'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/chart-datasets.json', 'utf8')) as {
  datasets: Record<string, { case: string; dataset: AnalysisDataset }>
}
const NAMES = Object.keys(FIXTURE.datasets)
const dataset = (name: string) => structuredClone(FIXTURE.datasets[name].dataset)
/** The width a card plans at before it is measured, and in jsdom, which lays nothing out (TrendChartCard). */
const DEFAULT_WIDTH = 502

afterEach(() => {
  flags.v2 = true
  vi.mocked(exportPanelPng).mockClear().mockResolvedValue(true)
  vi.mocked(analytics.exportGenerated).mockClear()
  vi.mocked(toast.error).mockClear()
})

const cards = (container: HTMLElement) => [...container.querySelectorAll('section')]

/** Every string the plan prints in the SVG, as the renderer lays it out: one entry per text or tspan. */
function plannedStrings(model: ChartModel, layout: ChartLayout): string[] {
  const strings: string[] = []
  for (const box of layout.panels) {
    const { panel } = box
    if (box.captionY != null && panel.caption) strings.push(panel.caption)
    strings.push(...panel.axis.ticks.map(panel.axis.format.tick))
    strings.push(...box.bars.flatMap((bar) => (bar.label ? [bar.label.text] : [])), ...box.gaps.map((gap) => gap.text))
    strings.push(...box.nearZero.map((label) => label.text))
    for (const [band, arrow] of [[box.offAbove, '↑'], [box.offBelow, '↓']] as const) for (const item of band?.items ?? []) strings.push(arrow, item.text)
  }
  strings.push(...model.periods.flatMap((period) => period.tick))
  if (layout.stripTop != null) for (const row of model.strip) strings.push(row.short, ...model.periods.map((period) => row.cells[period.key]))
  if (model.notesBand) strings.push('Notes')
  strings.push(...noteGlyphs(model, layout).map((glyph) => glyph.text))
  return strings.filter(Boolean).sort()
}

function drawnStrings(svg: SVGSVGElement): string[] {
  return [...svg.querySelectorAll('text')]
    .flatMap((text) => (text.querySelector('tspan') ? [...text.querySelectorAll('tspan')] : [text]).map((node) => node.textContent ?? ''))
    .filter(Boolean)
    .sort()
}

const num = (element: Element, name: string) => Number(element.getAttribute(name))

/** The plan's checks on one drawn SVG (spec §6). */
function expectDrawsPlan(svg: SVGSVGElement, model: ChartModel, layout: ChartLayout, tokens: ChartTokens) {
  expect([num(svg, 'width'), num(svg, 'height')], 'the SVG is the plan’s size').toEqual([layout.width, layout.height])
  expect(svg.getAttribute('viewBox')).toBe(`0 0 ${layout.width} ${layout.height}`)

  // D12: every panel group carries its id, step and domain.
  const groups = [...svg.querySelectorAll('g[data-panel]')]
  expect(groups.map((group) => [group.getAttribute('data-panel'), group.getAttribute('data-axis-step'), group.getAttribute('data-axis-domain')]))
    .toEqual(layout.panels.map((box) => [box.panel.id, String(box.panel.axis.step), box.panel.axis.domain.join(',')]))

  layout.panels.forEach((box, p) => {
    const group = groups[p]
    // D11: the tick strings and positions are the model's; D5: each label's right edge sits 8 px left of the plot.
    const ticks = [...group.querySelectorAll('text[text-anchor="end"]')]
    expect(ticks.map((tick) => tick.textContent)).toEqual(box.panel.axis.ticks.map(box.panel.axis.format.tick))
    ticks.forEach((tick, t) => {
      expect(num(tick, 'y')).toBeCloseTo(box.y(box.panel.axis.ticks[t]), 9)
      expect(num(tick, 'x')).toBe(layout.gutter - 8)
      expect(tick.hasAttribute('textLength')).toBe(false)
    })
    // Gridlines on the half pixel, the zero rule in its own ink.
    // (A break mark's strokes take their group's surface stroke; the off-scale rule is dashed.)
    const rules = [...group.querySelectorAll('line[stroke]')].filter((line) => line.getAttribute('stroke-dasharray') == null)
    expect(rules.map((line) => [num(line, 'y1'), line.getAttribute('stroke')]))
      .toEqual(box.panel.axis.ticks.map((tick) => [Math.round(box.y(tick)) + 0.5, tick === 0 ? tokens.zero : tokens.grid]))

    // D14: every bar rect carries its value and zero rule, and lies on its value's side of it.
    const bars = [...group.querySelectorAll('rect[data-v]')]
    expect(bars).toHaveLength(box.bars.length)
    bars.forEach((rect, b) => {
      const v = num(rect, 'data-v')
      const zero = num(rect, 'data-zero')
      expect([v, zero, num(rect, 'y'), num(rect, 'height')]).toEqual([box.bars[b].value, box.bars[b].zero, box.bars[b].y, box.bars[b].height])
      if (v >= 0) expect(num(rect, 'y') + num(rect, 'height')).toBeLessThanOrEqual(zero + 1e-9)
      else expect(num(rect, 'y')).toBeGreaterThanOrEqual(zero - 1e-9)
    })
    // A clipped growth bar is broken in the surface colour (§4.1).
    const breaks = [...group.querySelectorAll('g[stroke-width="1.5"]')].filter((mark) => mark.getAttribute('stroke') === tokens.surface)
    expect(breaks).toHaveLength(box.bars.filter((bar) => bar.clipped).length)

    // D7: one marker per valued, in-domain point of each line, at its slot centre.
    for (const mark of box.panel.marks.filter((each) => each.kind === 'line')) {
      const drawn = [...group.querySelectorAll(`[data-series="${mark.seriesKey}"]:not(path[fill="none"])`)].filter((node) => node.closest('text') == null && node.tagName !== 'text')
      const expected = mark.points.filter((point) => point.value != null && !point.offscale)
      expect(drawn.map((node) => node.getAttribute('data-period')), `${mark.seriesKey} markers`).toEqual(expected.map((point) => point.period))
      // A line never joins across a gap: one path per run of two or more consecutive valued points.
      const runs: string[] = []
      let run: string[] = []
      for (const point of [...mark.points, { period: '', value: null }]) {
        if (point.value != null) run.push(point.period)
        else {
          if (run.length > 1) runs.push(run.join(' '))
          run = []
        }
      }
      const paths = [...group.querySelectorAll(`path[fill="none"][data-series="${mark.seriesKey}"]`)]
      expect(paths.map((path) => path.getAttribute('data-period')), `${mark.seriesKey} line runs`).toEqual(runs)
      for (const path of paths) expect(path.getAttribute('d')).toMatch(/^M[^M]*$/)
    }
  })

  // D4: a series colour paints only marks bound to their data, off-scale arrows, and the strip's swatches.
  const seriesColours = new Set(tokens.series)
  const coloured = [...svg.querySelectorAll('*')].filter((node) => seriesColours.has(node.getAttribute('fill') ?? '') || seriesColours.has(node.getAttribute('stroke') ?? ''))
  expect(coloured.length).toBeGreaterThan(0)
  for (const node of coloured) {
    if (node.closest('[data-strip]')) continue
    expect([node.getAttribute('data-series'), node.getAttribute('data-period')].every(Boolean), `${node.tagName} in a series colour names its data`).toBe(true)
  }
  // Literal paint only: the export serialises the plot without the page's CSS or variables.
  for (const node of svg.querySelectorAll('*')) {
    for (const name of ['fill', 'stroke']) {
      const paint = node.getAttribute(name)
      if (paint != null) expect(paint, `${node.tagName} ${name}`).toMatch(/^(#[0-9A-F]{6}|rgba\([^)]*\)|none)$/)
    }
    expect(node.getAttribute('style') ?? '').not.toContain('var(')
  }
  // D5: no axis domain, tick line or tag: every line is a gridline, an off-scale rule or a break stroke.
  expect(svg.querySelectorAll('line').length).toBe(
    layout.panels.reduce((sum, box) => sum + box.panel.axis.ticks.length + (box.offAbove ? 1 : 0) + (box.offBelow ? 1 : 0) + 2 * box.bars.filter((bar) => bar.clipped).length, 0))

  expect(drawnStrings(svg), 'every printed string is the plan’s, and only those').toEqual(plannedStrings(model, layout))
}

describe.each(NAMES)('%s: the renderer draws the plan', (name) => {
  for (const view of ['card', 'expanded'] as ChartView[]) {
    it(view, () => {
      const ds = dataset(name)
      const { container } = render(<TrendChartsV2 dataset={ds} />)
      const sections = cards(container)
      expect(sections, 'every chart keeps its card (§3.4)').toHaveLength(CHART_IDS.length)
      CHART_IDS.forEach((chart, i) => {
        const model = buildChartModel(chart, ds, resolveDataNotes(ds))
        const card = sections[i]
        expect(within(card).getByRole('heading', { level: 2 })).toHaveTextContent(model.title)
        if (model.unavailable) {
          expect(card.querySelector('svg[role="img"]')).toBeNull()
          expect(card).toHaveTextContent(model.unavailable)
          return
        }
        if (view === 'expanded') fireEvent.click(within(card).getByRole('button', { name: 'Expand chart' }))
        const svg = card.querySelector<SVGSVGElement>('[data-analysis-chart] > svg')!
        expect(svg.getAttribute('aria-label')).toBe(`${model.title} chart`)
        expectDrawsPlan(svg, model, layoutChart(model, DEFAULT_WIDTH, view), CHART_TOKENS.light)
      })
    })
  }
})

describe('the card around the plot', () => {
  it('lays the plan out at the card’s measured width, and follows it', () => {
    let measured = 342.6
    const width = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => measured)
    try {
      const ds = dataset('REGN_annual')
      const { container, unmount } = render(<TrendChartsV2 dataset={ds} />)
      const model = buildChartModel('topline', ds, resolveDataNotes(ds))
      const plot = container.querySelector<HTMLElement>('[data-analysis-chart]')!
      // The phone card is 342 px; REGN's labels need 465 (spec §0.5), so the plot widens and scrolls in its card.
      const phone = layoutChart(model, 342, 'card')
      expect(phone.width).toBe(465)
      expect(plot.style.width).toBe('465px')
      expect(plot.querySelector('svg')!.getAttribute('width')).toBe('465')
      expect(plot.parentElement).toHaveAttribute('data-analysis-chart-scroll')
      unmount()
      // A chart that fits takes the card's whole-pixel width, so the export draws it at its on-screen size.
      measured = 502.6
      const wide = render(<TrendChartsV2 dataset={ds} />).container
      const margins = wide.querySelectorAll<HTMLElement>('[data-analysis-chart]')[CHART_IDS.indexOf('margins')]
      expect(layoutChart(buildChartModel('margins', ds), 502, 'card').width).toBe(502)
      expect(margins.style.width).toBe('502px')
    } finally {
      width.mockRestore()
    }
  })

  it('the server holds each plot’s box at the desktop card’s width, and paints no text before its font (G4, D9)', () => {
    const ds = dataset('AAPL_annual')
    const html = renderToString(<TrendChartsV2 dataset={ds} exportEnabled />)
    for (const chart of CHART_IDS) {
      const model = buildChartModel(chart, ds)
      if (model.unavailable) continue
      const plan = layoutChart(model, DEFAULT_WIDTH, 'card')
      expect(html).toContain(`data-analysis-chart="${model.title.replace(/&/g, '&amp;')}" style="width:${plan.width}px;height:${plan.height}px"></div>`)
    }
    expect(html).not.toContain('<svg role="img"')
    expect(html).not.toMatch(/<svg width="\d+" height="320"/)
  })

  it('a chart that does not apply keeps the card’s height and says why (§3.4)', () => {
    const ds = dataset('JPM_annual')
    const model = buildChartModel('margins', ds)
    expect(model.unavailable).toBeTruthy()
    const { container } = render(<TrendChartsV2 dataset={ds} exportEnabled />)
    const card = cards(container)[CHART_IDS.indexOf('margins')]
    const sentence = within(card).getByText(model.unavailable!)
    expect(sentence.style.height).toBe(`${CARD_HEIGHT}px`)
    expect(within(card).queryByRole('button', { name: 'Download chart as PNG' })).toBeNull()
    expect(within(card).getByRole('button', { name: 'Expand chart' })).toBeInTheDocument()
  })

  it('says when no slot holds the values, under the plot (A4)', () => {
    const ds = dataset('REGN_annual')
    for (const series of ds.series) if (!series.percent) for (const point of [series, ...series.points]) point.unit = 'CHF'
    const model = buildChartModel('topline', ds)
    expect(layoutChart(model, DEFAULT_WIDTH, 'card').valuesDontFit).toBe(true)
    const { container } = render(<TrendChartsV2 dataset={ds} />)
    const [topline, ...rest] = cards(container)
    expect(within(topline).getByText(VALUES_DONT_FIT)).toBeInTheDocument()
    for (const card of rest) expect(within(card).queryByText(VALUES_DONT_FIT)).toBeNull()
  })

  it('the legend names every series with its latest value and swatch, and the footnotes carry their marks', () => {
    const ds = dataset('REGNPN_annual')
    const { container } = render(<TrendChartsV2 dataset={ds} />)
    CHART_IDS.forEach((chart, i) => {
      const model = buildChartModel(chart, ds)
      const card = cards(container)[i]
      const legend = model.legend.length ? within(card).getByRole('list', { name: 'Series' }) : null
      expect(legend ? within(legend).getAllByRole('listitem').map((item) => item.textContent) : [])
        .toEqual(model.legend.map((item) => `${item.label}${item.value ?? ''}`))
      for (const [j, item] of model.legend.entries()) {
        const swatch = legend!.querySelectorAll('li')[j].querySelector('svg')!
        const dashed = swatch.querySelector('line[stroke-dasharray]')
        if (item.absent || item.color == null) expect(dashed?.getAttribute('stroke')).toBe(CHART_TOKENS.light.tick)
        else expect(swatch.querySelector(`[fill="${CHART_TOKENS.light.series[item.color]}"]`)).not.toBeNull()
      }
      const footnotes = [...card.querySelectorAll('ul:not([aria-label]) > li')].map((item) => item.textContent)
      expect(footnotes).toEqual(model.footnotes.map((footnote) => `${footnote.mark}${footnote.text}`))
    })
  })

  it('expanding takes both grid columns and the expanded plan, and collapsing returns', () => {
    const ds = dataset('REGN_annual')
    const { container } = render(<TrendChartsV2 dataset={ds} />)
    const card = cards(container)[CHART_IDS.indexOf('margins')]
    const model = buildChartModel('margins', ds)
    const svg = () => card.querySelector('[data-analysis-chart] > svg')!
    expect(svg().getAttribute('height')).toBe('320')
    fireEvent.click(within(card).getByRole('button', { name: 'Expand chart' }))
    expect(card).toHaveClass('md:col-span-2')
    expect(Number(svg().getAttribute('height'))).toBe(layoutChart(model, DEFAULT_WIDTH, 'expanded').height)
    expect(Number(svg().getAttribute('height'))).toBeGreaterThan(520)
    const collapse = within(card).getByRole('button', { name: 'Collapse chart' })
    expect(collapse).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(collapse)
    expect(card).not.toHaveClass('md:col-span-2')
    expect(svg().getAttribute('height')).toBe('320')
  })

  it('draws the dark theme’s tokens', () => {
    const ds = dataset('PLUG_annual')
    const { container } = render(
      <ThemeContext.Provider value={{ theme: 'dark', toggleTheme: () => {} }}>
        <TrendChartsV2 dataset={ds} />
      </ThemeContext.Provider>
    )
    CHART_IDS.forEach((chart, i) => {
      const model = buildChartModel(chart, ds)
      if (model.unavailable) return
      expectDrawsPlan(cards(container)[i].querySelector<SVGSVGElement>('[data-analysis-chart] > svg')!, model, layoutChart(model, DEFAULT_WIDTH, 'card'), CHART_TOKENS.dark)
    })
    const fills = [...container.querySelectorAll('[data-series]')].map((node) => (node.getAttribute('fill') === 'none' ? node.getAttribute('stroke') : node.getAttribute('fill')))
    expect(fills.every((paint) => CHART_TOKENS.dark.series.includes(paint!))).toBe(true)
  })
})

describe('the plot waits for its font (G4)', () => {
  const plots = (container: HTMLElement) => container.querySelectorAll('[data-analysis-chart] > svg').length
  const withFonts = (fonts: Partial<FontFaceSet>) => Object.defineProperty(document, 'fonts', { configurable: true, value: fonts })

  afterEach(() => {
    Reflect.deleteProperty(document, 'fonts')
    vi.useRealTimers()
  })

  it('paints once Geist Mono loads, with the export inert until then', async () => {
    let loaded!: () => void
    const load = vi.fn(() => new Promise<FontFace[]>((resolve) => { loaded = () => resolve([]) }))
    withFonts({ check: () => false, load })
    const { container } = render(<TrendChartsV2 dataset={dataset('AAPL_annual')} exportEnabled />)
    expect(load).toHaveBeenCalledWith('11px "Geist Mono"')
    expect(plots(container)).toBe(0)
    const box = container.querySelector<HTMLElement>('[data-analysis-chart]')!
    expect(box.style.height).toBe('320px')
    for (const button of screen.getAllByRole('button', { name: 'Download chart as PNG' })) expect(button).toBeDisabled()
    await act(async () => loaded())
    expect(plots(container)).toBe(CHART_IDS.length)
    for (const button of screen.getAllByRole('button', { name: 'Download chart as PNG' })) expect(button).toBeEnabled()
  })

  it('paints after 1,500 ms when the font never arrives', () => {
    vi.useFakeTimers()
    withFonts({ check: () => false, load: () => new Promise<FontFace[]>(() => {}) })
    const { container } = render(<TrendChartsV2 dataset={dataset('AAPL_annual')} />)
    act(() => { vi.advanceTimersByTime(1499) })
    expect(plots(container)).toBe(0)
    act(() => { vi.advanceTimersByTime(1) })
    expect(plots(container)).toBe(CHART_IDS.length)
  })

  it('paints at once when the face is already loaded', () => {
    const load = vi.fn()
    withFonts({ check: (face: string) => face === '11px "Geist Mono"', load })
    const { container } = render(<TrendChartsV2 dataset={dataset('AAPL_annual')} />)
    expect(plots(container)).toBe(CHART_IDS.length)
    expect(load).not.toHaveBeenCalled()
  })
})

describe('the PNG export', () => {
  it('is offered on Pro only, and sends the plot with the card’s legend and footnotes', async () => {
    const ds = dataset('REGN_annual')
    const { container, rerender } = render(<TrendChartsV2 dataset={ds} />)
    expect(screen.queryByRole('button', { name: 'Download chart as PNG' })).toBeNull()
    rerender(<TrendChartsV2 dataset={ds} exportEnabled />)
    expect(screen.getAllByRole('button', { name: 'Download chart as PNG' })).toHaveLength(CHART_IDS.length)

    const chart = 'cash'
    const model = buildChartModel(chart, ds)
    const card = cards(container)[CHART_IDS.indexOf(chart)]
    await act(async () => fireEvent.click(within(card).getByRole('button', { name: 'Download chart as PNG' })))
    expect(exportPanelPng).toHaveBeenCalledTimes(1)
    const [plot, filename, options] = vi.mocked(exportPanelPng).mock.calls[0]
    expect(plot).toBe(card.querySelector('[data-analysis-chart]'))
    expect(plot.querySelector('svg')).toBe(card.querySelector('svg[role="img"]'))
    expect(filename).toMatch(/\.png$/)
    expect(options?.dark).toBe(false)
    expect(options?.header).toMatchObject({
      ticker: ds.ticker,
      title: model.title,
      legend: model.legend.filter((item) => item.color != null).map((item) => ({ label: item.label, color: CHART_TOKENS.light.series[item.color!] })),
      notes: [...model.footnotes.map((footnote) => (footnote.mark ? `${footnote.mark}  ${footnote.text}` : footnote.text)), FCF_DEFINITION],
    })
    expect(options?.header?.sourceNote).toMatch(/^Source: SEC filings via EarningsNerd · /)
    expect(options?.header?.disclosure).toContain('Not investment advice')
    expect(analytics.exportGenerated).toHaveBeenCalledWith(expect.objectContaining({ surface: 'analysis', format: 'png', panel: model.title }))
  })

  it('a chart without free cash flow leaves its definition out, and a failed export says so', async () => {
    vi.mocked(exportPanelPng).mockResolvedValueOnce(false)
    const ds = dataset('REGN_annual')
    const { container } = render(<TrendChartsV2 dataset={ds} exportEnabled />)
    const card = cards(container)[CHART_IDS.indexOf('margins')]
    await act(async () => fireEvent.click(within(card).getByRole('button', { name: 'Download chart as PNG' })))
    expect(vi.mocked(exportPanelPng).mock.calls[0][2]?.header?.notes).not.toContain(FCF_DEFINITION)
    expect(analytics.exportGenerated).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith('Could not create the chart image. Try again.')
  })
})

describe('the CHARTS_V2 switch in TrendCharts', () => {
  it('production builds with the flag unset: vercel.json, whose env reaches every deployment, never sets it (F66)', () => {
    const vercel = JSON.parse(readFileSync('vercel.json', 'utf8')) as { env?: Record<string, string> }
    expect(vercel.env).toBeDefined()
    expect(Object.keys(vercel.env!)).not.toContain('NEXT_PUBLIC_CHARTS_V2')
  })

  it('on, the spec renderer draws every chart', async () => {
    const { container } = render(<TrendCharts dataset={dataset('AAPL_annual')} />)
    await waitFor(() => expect(container.querySelectorAll('svg[role="img"] g[data-panel]').length).toBeGreaterThan(0))
    expect(cards(container)).toHaveLength(CHART_IDS.length)
    expect(container.querySelector('[data-recharts]')).toBeNull()
  })

  it('off, today’s Recharts grid draws and the spec renderer is not loaded', () => {
    flags.v2 = false
    const { container } = render(<TrendCharts dataset={dataset('AAPL_annual')} />)
    expect(container.querySelector('[data-recharts]')).not.toBeNull()
    expect(container.querySelector('g[data-panel]')).toBeNull()
  })
})
