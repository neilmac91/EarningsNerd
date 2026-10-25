import { expect, type Locator, type Page } from '@playwright/test'
import type { TextRole } from '../../../features/analysis/components/TrendChartSvg'
import { apcaLc } from '../../unit/apca'

/**
 * The trend charts' DOM checks in a browser (docs/design/analysis-trend-charts-spec-2026-10.md §6), on the spec renderer
 * (NEXT_PUBLIC_CHARTS_V2), shared by charts-v2.spec.ts and charts-v2-gallery.spec.ts. measurePlot reads one plot in the
 * page; expectSound and expectInks hold it to the checks that need real text metrics, layout and computed colours:
 * - D1: every text box lies inside its SVG (at its edge: the spec's own layout sets captions and "Notes" at x = 0);
 * - D2: no two text boxes intersect;
 * - D3: inside a plot rect, only a bar label, an A13b label or a gap's "—"/"n/m" on its zero rule;
 * - D5: every y tick label ends left of the plot;
 * - D6: every paint clears its §3.8 APCA floor on the card's computed background (expectInks);
 * - D8: every string paints at Geist Mono's 0.6 em advance, so the planner's widths are the screen's;
 * - D10: no chart animates under reduced motion;
 * - D14: every bar lies on its value's side of its zero rule, at the page's width;
 * - M6 on the page: a plot fills its card, or is wider and scrolls inside it as a keyboard stop, opened at its newest
 *   period behind A7's sticky gutter, which repeats the y axis at the viewport's edge and passes D1, D2 and D8 itself.
 */

/** The planner's advance: Geist Mono is 0.6 em at 11 px (layout.ts ADVANCE). */
export const ADVANCE = 0.6 * 11

interface TextReport {
  outside: string[]
  collisions: string[]
  advances: string[]
}

/** A paint and the floor its kind takes (§3.8): data marks and the zero rule, must-read text, printed values, gridlines. */
export interface Paint {
  what: string
  floor: 'marks' | 'text' | 'values' | 'grid'
  /** The computed colour, `rgb(…)`. */
  colour: string
}

export interface PlotReport extends TextReport {
  name: string
  /** The width the card planned at: its viewport's whole-pixel width (TrendChartPlot). */
  measured: number
  height: number
  animations: number
  svgWidth: number
  viewportWidth: number
  scrolls: boolean
  /** How far the viewport sits from its newest period (0 there). */
  fromNewest: number
  keyboardStop: boolean
  /** A7's sticky gutter, while the plot's own has scrolled away: its text, and its left edge against the viewport's. */
  gutter: (TextReport & { offset: number; ticks: string[]; plotTicks: string[] }) | null
  /** D3, D5 and D14's failures. */
  inside: string[]
  offZero: string[]
  tickOverrun: string[]
  wrongSide: string[]
  /** Every text, `role|string|fill attribute`, sorted per role. */
  texts: Partial<Record<TextRole, string[]>>
  paints: Paint[]
}

/** Every chart plot in `scope` (the page, or one card), measured in the page. */
export async function measurePlots(scope: Page | Locator): Promise<PlotReport[]> {
  return scope.locator('[data-analysis-chart]').evaluateAll((plots, advance) => plots.map((plot) => {
    // D1, D2 and D8 on one SVG's text.
    const textOf = (svg: SVGSVGElement) => {
      const [, , width, height] = svg.getAttribute('viewBox')!.split(' ').map(Number)
      const texts = [...svg.querySelectorAll('text')]
      const boxes = texts.map((text) => ({ text: text.textContent ?? '', box: text.getBBox() }))
      const where = ({ text, box }: { text: string; box: DOMRect }) => `"${text}" at ${box.x.toFixed(1)},${box.y.toFixed(1)} ${box.width.toFixed(1)}×${box.height.toFixed(1)}`
      const outside = boxes.filter(({ box }) => box.x < -0.01 || box.y < -0.01 || box.x + box.width > width + 0.01 || box.y + box.height > height + 0.01).map(where)
      const collisions: string[] = []
      boxes.forEach((a, i) => boxes.slice(i + 1).forEach((b) => {
        const x = Math.min(a.box.x + a.box.width, b.box.x + b.box.width) - Math.max(a.box.x, b.box.x)
        const y = Math.min(a.box.y + a.box.height, b.box.y + b.box.height) - Math.max(a.box.y, b.box.y)
        if (x > 0.01 && y > 0.01) collisions.push(`${where(a)} and ${where(b)}`)
      }))
      const advances = texts
        .flatMap((text) => (text.querySelector('tspan') ? [...text.querySelectorAll('tspan')] : [text]))
        .flatMap((node) => {
          const chars = [...(node.textContent ?? '')].length
          const painted = node.getComputedTextLength()
          return Math.abs(painted - advance * chars) > 0.5 ? [`"${node.textContent}" paints ${painted.toFixed(2)} px, not ${(advance * chars).toFixed(2)}`] : []
        })
      return { width, height, outside, collisions, advances }
    }
    const svg = plot.querySelector('svg')!
    const { width, height, ...text } = textOf(svg)
    const viewport = plot.closest<HTMLElement>('[data-analysis-chart-scroll]')!
    const overlay = viewport.querySelector<SVGSVGElement>('[data-chart-gutter] svg')
    const ticks = (root: SVGSVGElement) => [...root.querySelectorAll('text[text-anchor="end"]')].map((tick) => `${tick.textContent}@${tick.getAttribute('y')}`)

    const panels = [...svg.querySelectorAll('g[data-panel]')].map((group) => {
      const [x, y, w, h] = group.getAttribute('data-plot')!.split(' ').map(Number)
      return { group, id: group.getAttribute('data-panel')!, left: x, top: y, right: x + w, bottom: y + h }
    })
    const all = [...svg.querySelectorAll('text')]
    const role = (node: Element) => node.getAttribute('data-text') ?? '(none)'
    // D3: a text box that crosses a plot rect must be a bar label, an A13b label or a gap's glyph.
    const inside: string[] = []
    for (const node of all) {
      const box = node.getBBox()
      for (const plot of panels) {
        const across = Math.min(box.x + box.width, plot.right) - Math.max(box.x, plot.left)
        const down = Math.min(box.y + box.height, plot.bottom) - Math.max(box.y, plot.top)
        if (across > 0.01 && down > 0.01 && !['label', 'near-zero', 'gap'].includes(role(node))) inside.push(`${role(node)} "${node.textContent}" in ${plot.id}`)
      }
    }
    // A gap's glyph sits on its panel's zero rule: its baseline 3 px above the zero tick's line, which is on the half
    // pixel (gridY), so within a pixel.
    const offZero: string[] = []
    for (const plot of panels) {
      const zero = [...plot.group.querySelectorAll('line[stroke]:not([stroke-dasharray])')].find((line) => {
        const y = Number(line.getAttribute('y1'))
        return [...plot.group.querySelectorAll('text[data-text="tick"]')].some((tick) => /^[^1-9]*0(?:\.0+)?%?$/.test(tick.textContent ?? '') && Math.abs(Number(tick.getAttribute('y')) - y) <= 1)
      })
      for (const gap of plot.group.querySelectorAll('text[data-text="gap"]')) {
        if (!zero || Math.abs(Number(gap.getAttribute('y')) + 3 - Number(zero.getAttribute('y1'))) > 1) offZero.push(`"${gap.textContent}" at y ${gap.getAttribute('y')} in ${plot.id}`)
      }
    }
    // D5: a y tick label's box ends left of the plot.
    const tickOverrun = panels.flatMap((plot) => [...plot.group.querySelectorAll('text[data-text="tick"]')].flatMap((tick) => {
      const box = (tick as SVGTextElement).getBBox()
      return box.x + box.width < plot.left ? [] : [`"${tick.textContent}" ends at ${(box.x + box.width).toFixed(1)}, the plot starts at ${plot.left}`]
    }))
    // D14 at the page's width: every bar on its value's side of its zero rule.
    const wrongSide = [...svg.querySelectorAll('rect[data-v]')].flatMap((rect) => {
      const [v, zero, y, h] = ['data-v', 'data-zero', 'y', 'height'].map((name) => Number(rect.getAttribute(name)))
      return (v >= 0 ? y + h <= zero + 1e-9 : y >= zero - 1e-9) ? [] : [`${rect.getAttribute('data-series')} ${rect.getAttribute('data-period')}`]
    })
    const texts: Record<string, string[]> = {}
    for (const node of all) (texts[role(node)] ??= []).push(`${node.textContent}|${node.getAttribute('fill')}`)
    for (const list of Object.values(texts)) list.sort()

    // D6: each paint's computed colour, with the floor its kind takes.
    const TEXT_FLOOR: Record<string, 'marks' | 'text' | 'values'> = {
      caption: 'text', tick: 'text', x: 'text', gap: 'text', 'strip-name': 'text', notes: 'text', note: 'text',
      label: 'values', 'near-zero': 'values', 'off-value': 'values', strip: 'values', 'off-arrow': 'marks',
    }
    const paints: Array<{ what: string; floor: 'marks' | 'text' | 'values' | 'grid'; colour: string }> = []
    for (const node of all) paints.push({ what: `${role(node)} "${node.textContent}"`, floor: TEXT_FLOOR[role(node)] ?? 'text', colour: getComputedStyle(node).fill })
    for (const plot of panels) for (const line of plot.group.querySelectorAll('line[stroke]')) {
      // The zero tick's rule and A3b's dashed edge rules are marks; every other ruled line is a gridline. (A break mark's
      // strokes take their group's surface paint, a cut in the bar rather than a paint of its own.)
      const zeroTick = [...plot.group.querySelectorAll('text[data-text="tick"]')].some((tick) => /^[^1-9]*0(?:\.0+)?%?$/.test(tick.textContent ?? '') && Math.abs(Number(tick.getAttribute('y')) - Number(line.getAttribute('y1'))) <= 1)
      paints.push({ what: `${plot.id} rule at ${line.getAttribute('y1')}`, floor: zeroTick || line.hasAttribute('stroke-dasharray') ? 'marks' : 'grid', colour: getComputedStyle(line).stroke })
    }
    for (const mark of svg.querySelectorAll('[data-series]:not(text)')) {
      const style = getComputedStyle(mark)
      paints.push({ what: `mark ${mark.getAttribute('data-series')} ${mark.getAttribute('data-period')}`, floor: 'marks', colour: style.fill === 'none' ? style.stroke : style.fill })
    }

    return {
      name: plot.getAttribute('data-analysis-chart')!,
      measured: Math.floor(viewport.clientWidth),
      height,
      ...text,
      // The plot's own; the card's controls keep the design system's colour transitions (DESIGN_SYSTEM.md §11).
      animations: plot.getAnimations({ subtree: true }).length,
      svgWidth: width,
      viewportWidth: viewport.clientWidth,
      scrolls: viewport.scrollWidth > viewport.clientWidth + 1,
      fromNewest: viewport.scrollWidth - viewport.clientWidth - viewport.scrollLeft,
      keyboardStop: viewport.tabIndex === 0 && viewport.getAttribute('role') === 'region',
      gutter: overlay && {
        ...textOf(overlay),
        offset: overlay.getBoundingClientRect().left - viewport.getBoundingClientRect().left,
        ticks: ticks(overlay),
        plotTicks: ticks(svg),
      },
      inside,
      offZero,
      tickOverrun,
      wrongSide,
      texts,
      paints,
    }
  }), ADVANCE)
}

export function expectSound(report: PlotReport) {
  const { name } = report
  expect(report.outside, `${name}: D1, text outside the SVG`).toEqual([])
  expect(report.collisions, `${name}: D2, text boxes that intersect`).toEqual([])
  expect(report.inside, `${name}: D3, text inside a plot rect other than a value or a gap`).toEqual([])
  expect(report.offZero, `${name}: D3, a gap's glyph off its zero rule`).toEqual([])
  expect(report.tickOverrun, `${name}: D5, a tick label reaching the plot`).toEqual([])
  expect(report.advances, `${name}: D8, text not at Geist Mono's advance`).toEqual([])
  expect(report.animations, `${name}: D10, animations under reduced motion`).toBe(0)
  expect(report.wrongSide, `${name}: D14, bars across their zero rule`).toEqual([])
  // M6: the plot is laid out at its card's whole-pixel width, or at its wider minimum, and then scrolls in its card.
  expect(report.svgWidth, `${name}: the plot is at least its card's width`).toBeGreaterThanOrEqual(Math.floor(report.viewportWidth))
  expect(report.scrolls, `${name}: scrolls exactly when it is wider than its card`).toBe(report.svgWidth > report.viewportWidth + 1)
  expect(report.keyboardStop, `${name}: a scrolling plot is a keyboard stop, and only then`).toBe(report.scrolls)
  // A plot that scrolls opens at its newest period, the one the legend and the metrics table quote, behind A7's sticky
  // gutter: at the viewport's left edge, its text sound, its tick labels the plot's own.
  if (!report.scrolls) {
    expect(report.gutter, `${name}: no gutter overlay on a plot that fits`).toBeNull()
    return
  }
  expect(report.fromNewest, `${name}: opens at its newest period`).toBeLessThanOrEqual(1)
  expect(report.gutter, `${name}: the sticky gutter repeats the y axis`).not.toBeNull()
  const gutter = report.gutter!
  expect(Math.abs(gutter.offset), `${name}: the gutter sticks to the viewport's left edge`).toBeLessThanOrEqual(0.5)
  expect(gutter.outside, `${name}: D1 in the gutter`).toEqual([])
  expect(gutter.collisions, `${name}: D2 in the gutter`).toEqual([])
  expect(gutter.advances, `${name}: D8 in the gutter`).toEqual([])
  expect(gutter.ticks, `${name}: the gutter's tick labels are the plot's`).toEqual(gutter.plotTicks)
}

/** `rgb(r, g, b)` → `#RRGGBB`; an alpha paint fails, since every chart ink is opaque. */
export function hexOf(colour: string): string {
  const match = /^rgb\((\d+), (\d+), (\d+)\)$/.exec(colour)
  if (!match) throw new Error(`not an opaque computed colour: ${colour}`)
  return `#${match.slice(1).map((channel) => Number(channel).toString(16).padStart(2, '0')).join('').toUpperCase()}`
}

/** §3.8's floors, |Lc| on the card: marks and the zero rule 45, must-read text 60, printed values 75, gridlines 10–25. */
export const FLOORS = { marks: [45, Infinity], text: [60, Infinity], values: [75, Infinity], grid: [10, 25] } as const

/** D6: every paint clears its floor on `ground`, the card's computed background. */
export function expectInks(name: string, paints: Paint[], ground: string) {
  const short = paints.flatMap(({ what, floor, colour }) => {
    const lc = Math.abs(apcaLc(hexOf(colour), hexOf(ground)))
    const [low, high] = FLOORS[floor]
    return lc >= low && lc <= high ? [] : [`${what}: ${colour} is Lc ${lc.toFixed(1)}, ${floor} take ${low}${high === Infinity ? '+' : `–${high}`}`]
  })
  expect(short, `${name}: D6, paints off their floor`).toEqual([])
}
