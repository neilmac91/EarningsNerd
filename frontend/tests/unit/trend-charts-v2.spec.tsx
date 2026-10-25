/* =============================================================================
   trend-charts-v2.spec.tsx — the spec renderer (CHARTS_V2, E192) draws the engine's plan
   -----------------------------------------------------------------------------
   TrendChartSvg only paints what features/analysis/lib/charts plans, so these checks hold the DOM to the plan on every
   fixture dataset and chart: the spec's DOM checks that need no layout engine (docs/design/analysis-trend-charts-spec-
   2026-10.md §6: D4, D5, D7, D11, D12, D14), every printed string, and literal paint the PNG export can serialise. The
   card around it: the legend, footnotes, a chart that does not apply, the residual sentence, the export's header, the
   dark tokens, the expanded view, and the flag switch in TrendCharts. Reading a chart (E193): the values stop, its keys
   and edges, the tooltip and wash, Escape, the pointer and a tap, a new window, the sticky gutter and the subgrid. Text
   boxes, collisions, the font (D1, D2, D8) and the reading contract's geometry need a browser:
   tests/e2e/charts-v2.spec.ts.
============================================================================= */
import { execFileSync } from 'node:child_process'
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
import { CARD_HEIGHT, gutterCover, gutterCuts, gutterOverlayWidth, layoutChart, noteGlyphs, VALUES_DONT_FIT, type ChartLayout } from '@/features/analysis/lib/charts/layout'
import { buildChartModel, CHART_IDS, type ChartModel, type ChartView } from '@/features/analysis/lib/charts/model'
import { CHART_TOKENS, type ChartTokens } from '@/features/analysis/lib/charts/theme'
import { chartReadouts } from '@/features/analysis/lib/charts/readout'
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
  // The plan's 0.6 em advance holds only unhinted: full hinting at 1x snaps it to whole pixels (D8).
  expect(svg.getAttribute('text-rendering')).toBe('geometricPrecision')

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
      expect(plot.closest('[data-analysis-chart-scroll]')).not.toBeNull()
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
      const title = model.title.replace(/&/g, '&amp;')
      // The plot's box, the export's node, holds its size empty until the font has loaded.
      expect(html).toMatch(new RegExp(`data-analysis-chart="${title}"[^>]*style="width:${plan.width}px;height:${plan.height}px"></div>`))
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

  it('M14: the footnotes are the same strings in the card and expanded views, light and dark', () => {
    const ds = dataset('REGNPN_annual')
    const footnotes = (container: HTMLElement) => cards(container).map((card) => [...card.querySelectorAll('ul:not([aria-label]) > li')].map((item) => item.textContent))
    const light = render(<TrendChartsV2 dataset={ds} />)
    const card = footnotes(light.container)
    expect(card.flat().length).toBeGreaterThan(0)
    for (const section of cards(light.container)) fireEvent.click(within(section).getByRole('button', { name: 'Expand chart' }))
    expect(footnotes(light.container)).toEqual(card)
    light.unmount()
    const dark = render(
      <ThemeContext.Provider value={{ theme: 'dark', toggleTheme: () => {} }}>
        <TrendChartsV2 dataset={ds} />
      </ThemeContext.Provider>
    )
    expect(footnotes(dark.container)).toEqual(card)
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
  it('production builds with the flag unset: no committed build config sets it (F66)', () => {
    // vercel.json's env and build.env reach every deployment; next.config's env and a committed .env file are inlined
    // into every build. A preview sets the flag in Vercel's Preview environment instead. The examples document it.
    const tracked = execFileSync('git', ['ls-files', 'vercel.json', 'next.config.*', '.env*'], { encoding: 'utf8' }).split('\n').filter(Boolean)
    expect(tracked).toContain('vercel.json')
    expect(tracked.some((file) => file.startsWith('next.config.'))).toBe(true)
    const setting = tracked.filter((file) => !file.endsWith('.example') && readFileSync(file, 'utf8').includes('NEXT_PUBLIC_CHARTS_V2'))
    expect(setting).toEqual([])
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

describe('reading a chart a period at a time (E193; spec §3.9, §3.13; DESIGN_SYSTEM.md §10)', () => {
  const NAME = (title: string) => `${title} chart values`
  const setup = (name = 'REGN_annual', chart: (typeof CHART_IDS)[number] = 'balance') => {
    const ds = dataset(name)
    const utils = render(<TrendChartsV2 dataset={ds} />)
    const notes = resolveDataNotes(ds)
    const model = buildChartModel(chart, ds, notes)
    const card = cards(utils.container)[CHART_IDS.indexOf(chart)]
    const stop = within(card).getByRole('slider', { name: NAME(model.title) })
    // The plot under the values stop, which passes the pointer through to it.
    const plot = card.querySelector<HTMLElement>('[data-analysis-chart]')!
    const tooltip = () => card.querySelector<HTMLElement>('[data-chart-tooltip]')
    const wash = () => card.querySelector<HTMLElement>('[data-chart-wash]')
    const status = within(card).getByRole('status')
    return { ...utils, ds, model, card, stop, plot, tooltip, wash, status, readouts: chartReadouts(model, ds, notes) }
  }
  /** The pointer leaving the chart: React reads a leave from the pointerout into what lies outside. */
  const leave = (from: Element, pointerType: string) =>
    fireEvent(from, new PointerEvent('pointerout', { bubbles: true, relatedTarget: document.body, pointerType, pointerId: 1 }))
  /** Focus as a keyboard user arrives, with Tab: jsdom's :focus-visible follows the last key, and a printable one turns it
   *  off. */
  const tabTo = (element: HTMLElement) => {
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Tab' })
    act(() => element.focus())
  }
  /** A colour as the browser reads it back from a style. */
  const css = (property: 'color' | 'background', value: string) => {
    const probe = document.createElement('div')
    probe.style[property] = value
    return probe.style[property]
  }
  /** jsdom lays nothing out, so a pointer's client x is the stage's x. */
  const pointer = (target: Element, type: string, clientX: number, pointerType = 'mouse', clientY = 10) =>
    fireEvent(target, new PointerEvent(type, { bubbles: true, cancelable: true, clientX, clientY, pointerType, pointerId: 1 }))

  it('each drawn chart has one values stop, a slider at the newest period whose value text is its readout', () => {
    const ds = dataset('JPM_annual')
    const { container } = render(<TrendChartsV2 dataset={ds} />)
    const notes = resolveDataNotes(ds)
    CHART_IDS.forEach((chart, i) => {
      const card = cards(container)[i]
      const model = buildChartModel(chart, ds, notes)
      if (model.unavailable) {
        expect(within(card).queryByRole('slider'), 'a chart that does not apply has nothing to read').toBeNull()
        return
      }
      const stop = within(card).getByRole('slider', { name: NAME(model.title) })
      const readouts = chartReadouts(model, ds, notes)
      expect(stop).toHaveAttribute('tabindex', '0')
      expect([stop.getAttribute('aria-valuemin'), stop.getAttribute('aria-valuemax'), stop.getAttribute('aria-valuenow')])
        .toEqual(['0', String(model.periods.length - 1), String(model.periods.length - 1)])
      expect(stop).toHaveAttribute('aria-valuetext', readouts.at(-1)!.announcement)
      // A layer over the viewport, after it in the Tab order, holding nothing; the export's node holds the chart's SVG
      // alone, without the tooltip, wash or gutter.
      const viewport = card.querySelector('[data-analysis-chart-scroll]')!
      expect(stop.childElementCount).toBe(0)
      expect(stop).toHaveClass('pointer-events-none', 'absolute', 'inset-0', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark')
      expect(stop.parentElement).toBe(viewport.parentElement)
      expect(viewport.compareDocumentPosition(stop) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect([...card.querySelector('[data-analysis-chart]')!.children].map((child) => child.tagName.toLowerCase())).toEqual(['svg'])
      expect(card.querySelectorAll('[tabindex="0"]')).toHaveLength(1)
    })
  })

  it('Left and Right step a period, Down and Up too, Home and End jump, and the keys never scroll natively', () => {
    const { stop, readouts } = setup()
    const last = readouts.length - 1
    const at = () => Number(stop.getAttribute('aria-valuenow'))
    expect(fireEvent.keyDown(stop, { key: 'ArrowLeft' }), 'default prevented').toBe(false)
    expect(at()).toBe(last - 1)
    expect(stop).toHaveAttribute('aria-valuetext', readouts[last - 1].announcement)
    fireEvent.keyDown(stop, { key: 'ArrowDown' })
    expect(at()).toBe(last - 2)
    fireEvent.keyDown(stop, { key: 'ArrowUp' })
    fireEvent.keyDown(stop, { key: 'ArrowRight' })
    expect(at()).toBe(last)
    expect(fireEvent.keyDown(stop, { key: 'Home' })).toBe(false)
    expect(at()).toBe(0)
    expect(stop).toHaveAttribute('aria-valuetext', readouts[0].announcement)
    fireEvent.keyDown(stop, { key: 'End' })
    expect(at()).toBe(last)
    expect(fireEvent.keyDown(stop, { key: 'a' }), 'other keys are not the chart’s').toBe(true)
  })

  it('a step past either end says so in the status line, fresh on every press', async () => {
    const { stop, status } = setup()
    fireEvent.keyDown(stop, { key: 'ArrowRight' })
    await waitFor(() => expect(status).toHaveTextContent('Newest period.'))
    fireEvent.keyDown(stop, { key: 'ArrowRight' })
    expect(status, 'cleared, so the same words are spoken again').toHaveTextContent('')
    await waitFor(() => expect(status).toHaveTextContent('Newest period.'))
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    expect(status).toHaveTextContent('')
    fireEvent.keyDown(stop, { key: 'Home' })
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    await waitFor(() => expect(status).toHaveTextContent('Oldest period.'))
    // A move off the edge, or a blur, before the word lands cancels it: it never speaks for a period it is not on.
    const frame = () => act(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    fireEvent.keyDown(stop, { key: 'ArrowRight' })
    await frame()
    expect(status).toHaveTextContent('')
    fireEvent.keyDown(stop, { key: 'Home' })
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    fireEvent.blur(stop)
    await frame()
    expect(status).toHaveTextContent('')
  })

  it('the keyboard’s period shows its tooltip and its column wash, both hidden from screen readers', () => {
    const { stop, tooltip, wash, readouts, model } = setup('PGR_quarterly', 'topline')
    expect(tooltip()).toBeNull()
    tabTo(stop)
    const last = readouts.length - 1
    const layout = layoutChart(model, DEFAULT_WIDTH, 'card')
    expect(tooltip()).toHaveAttribute('aria-hidden', 'true')
    expect(tooltip()!.querySelector('p')).toHaveTextContent(readouts[last].header)
    expect([...tooltip()!.querySelectorAll('li')].map((row) => row.textContent)).toEqual(readouts[last].rows.map((row) => `${row.label}${row.text}`))
    expect(wash()).toHaveAttribute('aria-hidden', 'true')
    expect([wash()!.style.left, wash()!.style.width, wash()!.style.height])
      .toEqual([`${layout.x(model.periods[last].key) - layout.slot / 2}px`, `${layout.slot}px`, `${layout.height}px`])
    expect(wash()!.style.background).toBe(css('background', CHART_TOKENS.light.cursor))
    fireEvent.keyDown(stop, { key: 'Home' })
    expect(tooltip()!.querySelector('p')).toHaveTextContent(readouts[0].header)
    expect(wash()!.style.left).toBe(`${layout.x(model.periods[0].key) - layout.slot / 2}px`)
    // Focus leaving hides the keyboard's tooltip and keeps its period.
    act(() => stop.blur())
    expect(tooltip()).toBeNull()
    expect(wash()).toBeNull()
    expect(stop).toHaveAttribute('aria-valuenow', '0')
  })

  it('a review note’s letter takes the review ink in the tooltip, as in the notes band; a calculated value says so', () => {
    const ds = dataset('REGNPN_annual')
    const { container } = render(<TrendChartsV2 dataset={ds} />)
    const card = cards(container)[CHART_IDS.indexOf('cash')]
    const stop = within(card).getByRole('slider')
    tabTo(stop)
    const row = [...card.querySelectorAll('[data-chart-tooltip] li')].find((item) => item.textContent?.startsWith('Free cash flow'))!
    expect(row).toHaveTextContent('· Calculated (a)')
    const letter = [...row.querySelectorAll('span')].find((span) => span.textContent === ' (a)')!
    const note = resolveDataNotes(ds).notes.find((candidate) => candidate.letter === 'a')!
    expect(note.kind, 'REGNPN’s simulated flags are review notes').toBe('review')
    expect(letter.style.color).toBe(css('color', CHART_TOKENS.light.review))
  })

  it('Escape dismisses the tooltip first, then collapses an expanded card and returns focus to its toggle', () => {
    const { card, stop, tooltip } = setup()
    fireEvent.click(within(card).getByRole('button', { name: 'Expand chart' }))
    tabTo(stop)
    expect(tooltip()).not.toBeNull()
    expect(fireEvent.keyDown(stop, { key: 'Escape' })).toBe(false)
    expect(tooltip()).toBeNull()
    expect(card, 'the first Escape closes the tooltip alone').toHaveClass('md:col-span-2')
    fireEvent.keyDown(stop, { key: 'Escape' })
    expect(card).not.toHaveClass('md:col-span-2')
    const toggle = within(card).getByRole('button', { name: 'Expand chart' })
    expect(toggle).toHaveFocus()
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    // Collapsed, Escape is not the card's.
    expect(fireEvent.keyDown(toggle, { key: 'Escape' })).toBe(true)
  })

  it('a pointer reads the period under it, never the gutter; the next key resumes the keyboard’s own period', () => {
    const { stop, plot, tooltip, readouts, model } = setup()
    const layout = layoutChart(model, DEFAULT_WIDTH, 'card')
    const last = readouts.length - 1
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    pointer(plot, 'pointermove', layout.plotLeft + layout.slot * 2 + 1)
    expect(tooltip()!.querySelector('p')).toHaveTextContent(readouts[2].header)
    expect(stop, 'pointing moves no keyboard period').toHaveAttribute('aria-valuenow', String(last - 1))
    // Resting on the tooltip keeps its period (WCAG 1.4.13), wherever the tooltip lies.
    pointer(tooltip()!, 'pointermove', layout.plotLeft + layout.slot * 6 + 1)
    expect(tooltip()!.querySelector('p')).toHaveTextContent(readouts[2].header)
    pointer(plot, 'pointermove', layout.plotLeft - 1)
    expect(tooltip(), 'the gutter is no period').toBeNull()
    pointer(plot, 'pointermove', layout.plotLeft + layout.slot * 2 + 1)
    fireEvent.keyDown(stop, { key: 'ArrowRight' })
    expect(stop).toHaveAttribute('aria-valuenow', String(last))
    expect(tooltip()!.querySelector('p')).toHaveTextContent(readouts[last].header)
    pointer(plot, 'pointermove', layout.plotLeft + 1)
    leave(plot, 'mouse')
    expect(tooltip()).toBeNull()
  })

  it('Escape closes a pointer’s tooltip wherever focus is', () => {
    const { card, plot, tooltip, model } = setup()
    const layout = layoutChart(model, DEFAULT_WIDTH, 'expanded')
    fireEvent.click(within(card).getByRole('button', { name: 'Expand chart' }))
    pointer(plot, 'pointermove', layout.plotLeft + 1)
    expect(tooltip()).not.toBeNull()
    const toggle = within(card).getByRole('button', { name: 'Collapse chart' })
    tabTo(toggle)
    fireEvent.keyDown(toggle, { key: 'Escape' })
    expect(tooltip()).toBeNull()
    expect(card, 'the tooltip took that Escape').toHaveClass('md:col-span-2')
  })

  it('a tap pins its period’s tooltip until a second tap or a press outside; a swipe pins nothing', () => {
    const { plot, tooltip, readouts, model } = setup()
    const layout = layoutChart(model, DEFAULT_WIDTH, 'card')
    const tap = (x: number, endX = x) => {
      pointer(plot, 'pointerdown', x, 'touch')
      pointer(plot, 'pointerup', endX, 'touch')
    }
    tap(layout.plotLeft + layout.slot * 3 + 2, layout.plotLeft + layout.slot * 3 + 40)
    expect(tooltip(), 'a swipe').toBeNull()
    tap(layout.plotLeft + layout.slot * 3 + 2)
    expect(tooltip()!.querySelector('p')).toHaveTextContent(readouts[3].header)
    leave(plot, 'touch')
    expect(tooltip(), 'a lifted finger leaves the cell; the tooltip stays').not.toBeNull()
    tap(layout.plotLeft + layout.slot * 3 + 4)
    expect(tooltip(), 'a second tap on its period').toBeNull()
    tap(layout.plotLeft + layout.slot * 4 + 2)
    expect(tooltip()).not.toBeNull()
    fireEvent(document.body, new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' }))
    expect(tooltip(), 'a press outside the chart').toBeNull()
  })

  it('a new window starts again at its newest period, even when it holds the period the keyboard was on', () => {
    const { stop, rerender, ds } = setup()
    const last = ds.periods.length - 1
    // The second-newest period, which the narrower window below still holds.
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    expect(stop).toHaveAttribute('aria-valuenow', String(last - 1))
    const narrow = structuredClone(ds)
    narrow.periods = narrow.periods.slice(-4)
    rerender(<TrendChartsV2 dataset={narrow} />)
    expect(stop).toHaveAttribute('aria-valuemax', '3')
    expect(stop).toHaveAttribute('aria-valuenow', '3')
    // And one that no longer holds it.
    fireEvent.keyDown(stop, { key: 'Home' })
    rerender(<TrendChartsV2 dataset={dataset('REGN_annual')} />)
    expect(stop).toHaveAttribute('aria-valuenow', String(last))
  })

  it('a plot that scrolls opens at its newest period, behind a sticky gutter that repeats its y axis', () => {
    const viewportWidth = 300
    const scroll = vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
      return this.hasAttribute('data-analysis-chart-scroll') ? (this.firstElementChild as HTMLElement).offsetWidth || Number.parseFloat((this.firstElementChild as HTMLElement).style.width) : 0
    })
    const width = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) {
      return this.hasAttribute('data-analysis-chart-scroll') ? viewportWidth : 0
    })
    try {
      const { card, model, plot, ds } = setup('REGN_annual', 'topline')
      const viewport = card.querySelector<HTMLElement>('[data-analysis-chart-scroll]')!
      const layout = layoutChart(model, viewportWidth, 'card')
      expect(layout.width).toBeGreaterThan(viewportWidth)
      expect(viewport).toHaveAttribute('role', 'region')
      expect(viewport.scrollLeft, 'opened at the newest period').toBe(layout.width)
      const gutter = card.querySelector<HTMLElement>('[data-chart-gutter]')!
      expect(gutter).toHaveAttribute('aria-hidden', 'true')
      expect(plot.contains(gutter), 'outside the node the export serialises').toBe(false)
      const svg = gutter.querySelector('svg')!
      expect(Number(svg.getAttribute('width'))).toBe(gutterOverlayWidth(layout, gutterCover(layout, viewport.scrollLeft)))
      expect(Number(svg.getAttribute('width'))).toBeGreaterThan(layout.plotLeft)
      // Its text: the plot's captions and tick labels at the plot's positions, and the band's "Notes".
      const plotted = [...plot.querySelectorAll('svg > g[data-panel] text')].filter((text) => Number(text.getAttribute('x')) < layout.plotLeft || text.getAttribute('text-anchor') === 'end')
      const repeated = [...svg.querySelectorAll('text')].filter((text) => text.textContent !== 'Notes')
      expect(repeated.map((text) => [text.textContent, text.getAttribute('x'), text.getAttribute('y')]))
        .toEqual(plotted.map((text) => [text.textContent, text.getAttribute('x'), text.getAttribute('y')]))
      expect([...svg.querySelectorAll('text')].some((text) => text.textContent === 'Notes')).toBe(model.notesBand != null)
      // Scrolled into a column, the gutter covers that whole column, its gridlines carried across, and a pointer there
      // reads no period.
      viewport.scrollLeft = layout.slot * 2 + 5
      fireEvent.scroll(viewport)
      const cover = gutterCover(layout, viewport.scrollLeft)
      expect(cover).toBeCloseTo(layout.plotLeft + layout.slot - 5, 9)
      const surface = card.querySelector('[data-chart-gutter] svg > rect')!
      expect(Number(surface.getAttribute('width'))).toBeCloseTo(cover, 9)
      const rules = [...card.querySelectorAll('[data-chart-gutter] svg line')]
      expect(rules.length).toBeGreaterThan(0)
      for (const rule of rules) expect([Number(rule.getAttribute('x1')), Number(rule.getAttribute('x2'))]).toEqual([layout.plotLeft, cover])
      // A browser moves the scrolled stage left by the scroll; jsdom lays nothing out.
      vi.spyOn(viewport.firstElementChild!, 'getBoundingClientRect').mockReturnValue(new DOMRect(-viewport.scrollLeft, 0, layout.width, layout.height))
      fireEvent(plot, new PointerEvent('pointermove', { bubbles: true, clientX: cover - 1, clientY: 10, pointerType: 'mouse' }))
      expect(card.querySelector('[data-chart-tooltip]'), 'under the cover').toBeNull()
      fireEvent(plot, new PointerEvent('pointermove', { bubbles: true, clientX: cover + 1, clientY: 10, pointerType: 'mouse' }))
      expect(card.querySelector('[data-chart-tooltip] p')).toHaveTextContent(chartReadouts(model, ds, resolveDataNotes(ds))[3].header)
      // Scrolled back to the start, the plot's own axis shows and the gutter goes.
      viewport.scrollLeft = 0
      fireEvent.scroll(viewport)
      expect(card.querySelector('[data-chart-gutter]')).toBeNull()
    } finally {
      scroll.mockRestore()
      width.mockRestore()
    }
  })

  it('a plot opens at its newest period whenever a view or window starts to overflow; a resize keeps the reader’s place', () => {
    // Each viewport's width by view, and a ResizeObserver the test fires (vitest.setup's never calls back).
    const widths = { card: 300, expanded: 1100 }
    const scroll = vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
      return this.hasAttribute('data-analysis-chart-scroll') ? Number.parseFloat((this.firstElementChild as HTMLElement).style.width) : 0
    })
    const width = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) {
      if (!this.hasAttribute('data-analysis-chart-scroll')) return 0
      return this.closest('section')!.classList.contains('md:col-span-2') ? widths.expanded : widths.card
    })
    const observers: (() => void)[] = []
    const Original = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor(callback: () => void) { observers.push(callback) }
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver
    // The browser measures after each layout; it also brings a scroll that no longer fits back to 0.
    const settle = () => act(() => observers.forEach((callback) => callback()))
    try {
      const { card, ds, rerender } = setup('REGN_annual', 'topline')
      const viewport = () => card.querySelector<HTMLElement>('[data-analysis-chart-scroll]')!
      const newest = () => Number.parseFloat((viewport().firstElementChild as HTMLElement).style.width)
      settle()
      expect(viewport()).toHaveAttribute('role', 'region')
      expect(viewport().scrollLeft, 'the first layout').toBe(newest())
      // A resize or a zoom that keeps the plot overflowing keeps the reader's place.
      viewport().scrollLeft = 40
      fireEvent.scroll(viewport())
      widths.card = 320
      settle()
      fireEvent(window, new Event('resize'))
      expect(viewport().scrollLeft, 'a resize').toBe(40)
      // Expanded, the plot fits; collapsed, the card opens at its newest period again (§3.10).
      fireEvent.click(within(card).getByRole('button', { name: 'Expand chart' }))
      settle()
      expect(viewport(), 'the expanded plot fits').not.toHaveAttribute('role')
      viewport().scrollLeft = 0
      fireEvent.click(within(card).getByRole('button', { name: 'Collapse chart' }))
      settle()
      expect(viewport().scrollLeft, 'collapsed from a view that fits').toBe(newest())
      // On a phone both views overflow, and each opens at its newest period.
      widths.expanded = 300
      viewport().scrollLeft = 40
      fireEvent.click(within(card).getByRole('button', { name: 'Expand chart' }))
      settle()
      expect(viewport()).toHaveAttribute('role', 'region')
      expect(viewport().scrollLeft, 'expanded').toBe(newest())
      viewport().scrollLeft = 40
      fireEvent.click(within(card).getByRole('button', { name: 'Collapse chart' }))
      settle()
      expect(viewport().scrollLeft, 'collapsed').toBe(newest())
      // A new window opens at its newest period.
      viewport().scrollLeft = 40
      const narrow = structuredClone(ds)
      narrow.periods = narrow.periods.slice(-8)
      rerender(<TrendChartsV2 dataset={narrow} />)
      settle()
      expect(viewport().scrollLeft, 'a new window').toBe(newest())
    } finally {
      globalThis.ResizeObserver = Original
      scroll.mockRestore()
      width.mockRestore()
    }
  })

  it('the sticky gutter hides whole a value its edge cuts: an off-scale value wider than its column', () => {
    const viewportWidth = 300
    const scroll = vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
      return this.hasAttribute('data-analysis-chart-scroll') ? Number.parseFloat((this.firstElementChild as HTMLElement).style.width) : 0
    })
    const width = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) {
      return this.hasAttribute('data-analysis-chart-scroll') ? viewportWidth : 0
    })
    try {
      // SNAP's margins clip their 2017 outliers, printed at the plot's edge wider than a 36 px column (−422.5%).
      const { card, model } = setup('SNAP_annual', 'margins')
      const layout = layoutChart(model, viewportWidth, 'card')
      const viewport = card.querySelector<HTMLElement>('[data-analysis-chart-scroll]')!
      // The first scroll at which the cover's edge cuts an off-scale value.
      let at = 1
      while (!gutterCuts(layout, at, gutterCover(layout, at)).length) at++
      expect(at).toBeLessThan(layout.width - viewportWidth)
      viewport.scrollLeft = at
      fireEvent.scroll(viewport)
      const cuts = gutterCuts(layout, at, gutterCover(layout, at))
      const drawn = [...card.querySelectorAll('[data-chart-gutter] rect[data-cut]')]
      expect(drawn.map((rect) => ['x', 'y', 'width', 'height'].map((name) => Number(rect.getAttribute(name)))))
        .toEqual(cuts.map((cut) => [cut.x, cut.y, cut.width, cut.height]))
      const svg = card.querySelector('[data-chart-gutter] svg')!
      expect(Number(svg.getAttribute('width'))).toBe(gutterOverlayWidth(layout, gutterCover(layout, at), cuts))
    } finally {
      scroll.mockRestore()
      width.mockRestore()
    }
  })

  it.each(['REGN_annual', 'JPM_annual'])('%s: a grid row’s cards share its rows: header, plot, notes (the subgrid)', (name) => {
    // JPM's margins do not apply: its card keeps the three rows, the sentence in the plot's.
    const { container } = render(<TrendChartsV2 dataset={dataset(name)} />)
    for (const card of cards(container)) {
      expect(card).toHaveClass('row-span-3', 'grid', 'grid-cols-1', 'grid-rows-subgrid', 'gap-y-0')
      const flow = [...card.children].filter((child) => !child.classList.contains('sr-only'))
      expect(flow, 'three rows in flow').toHaveLength(3)
    }
  })
})
