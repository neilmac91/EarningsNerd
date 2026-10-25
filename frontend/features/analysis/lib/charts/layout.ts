/**
 * The trend charts' geometry (docs/design/analysis-trend-charts-spec-2026-10.md §3.7, A3b, A4, A6, A7, A13,
 * A13b). Every SVG text is 11 px Geist Mono, whose 0.6 em advance makes each width arithmetic, so the plan
 * is the same on the server, in tests and in the PNG export, and every text box is placed in a band of
 * known height before render (rule L1: no text outside its band). Card and expanded heights depend on the
 * view and mode only, never on the width.
 */
import type { ChartModel, ChartView, ModelMark, ModelPanel, NoteGlyph } from './model'
import { compactMoney, linear } from './scale'

export const FONT_PX = 11
export const ADVANCE = FONT_PX * 0.6
export const textWidth = (text: string) => [...text].length * ADVANCE

const HEIGHT: Record<ChartView, number> = { card: 320, expanded: 520 }
/** A card's height, the same for a chart that draws and one that says why it does not (D13). */
export const CARD_HEIGHT = HEIGHT.card
const CAPTION = 14
const LABEL_PAD = 14
const TICK_PAD = 8
/** Off-scale band row pitch: an 11 px line box is about 13 px tall, so rows sit 14 px apart. */
export const OFF_ROW = 14
/** The ↑/↓ glyph and its gap before an off-scale value. */
export const OFF_GLYPH = 9
const STRIP_ROW = 16
const NOTES_ROW = 16
const BOTTOM = 4
const RIGHT_PAD = 8
/** The narrowest period slot: below it the chart scrolls inside its own viewport, never the page. */
export const MIN_SLOT = 36
/** A labelled chart (the top line's) widens its slot past MIN_SLOT until A4 finds a label tier, up to this. On the
 *  audit's 72 top lines, 66 fit at 36 px and the other six (LCID, NVDA, PLUG, REGN, REGNPN and RIVN, all annual)
 *  needed at most 41.7 px: six-glyph labels such as "$4.86B" cannot keep 2 px apart at a 36 px pitch. Past it, as
 *  a code-prefixed currency's labels ("CHF 4.9B") can be, the card says VALUES_DONT_FIT instead. */
export const LABELLED_MAX_SLOT = 42
/** The value strip's row: its series' swatch centred at STRIP_MARKER_X, then its short name from STRIP_LABEL_X. */
export const STRIP_MARKER_X = 6
export const STRIP_LABEL_X = 14
/** What the card says under the SVG when A4 finds no label tier for a panel, even at LABELLED_MAX_SLOT (spec §3.7).
 *  It does not offer the expanded view: on a phone that view is no wider. */
export const VALUES_DONT_FIT = 'Values don’t fit at this width. The metrics table lists them.'

export interface LabelPlan {
  /** One decimal tier for the whole panel, or null when no tier fits: the panel prints no labels and the card says
   *  VALUES_DONT_FIT. */
  decimals: number | null
}

export interface OffItem {
  period: string
  seriesKey: string
  color: number
  text: string
  x: number
  /** The glyph's x; the value starts at left + OFF_GLYPH. Clamped so the pair stays inside the SVG. */
  left: number
  row: number
}

export interface OffBand {
  top: number
  depth: number
  items: OffItem[]
}

export interface NearZeroLabel {
  period: string
  x: number
  /** Baseline. */
  y: number
  text: string
}

export interface PlacedBar {
  period: string
  seriesKey: string
  value: number
  /** The rect (A13): anchored at the zero rule on the value's side, never across it, and at least 2 px long. */
  x: number
  y: number
  width: number
  height: number
  /** The zero rule's y, the bar's anchor. */
  zero: number
  /** Zero, or a true length under 2 px: drawn as the 2 px minimum. */
  stub: boolean
  /** The value runs past the axis (a clipped growth bar), so the renderer draws the break mark. */
  clipped: boolean
  /** The printed value and its baseline (A4), or null when the panel prints none. */
  label: { text: string; y: number } | null
}

/** A bar slot with no value prints "—" (missing) or "n/m" (not meaningful) on the zero rule. */
export interface SlotText {
  period: string
  text: '—' | 'n/m'
  x: number
  /** Baseline. */
  y: number
}

export interface PanelBox {
  panel: ModelPanel
  /** First y of this panel's bands (caption, off-scale rows, pad); panel i owns [regionTop_i, regionTop_i+1). */
  regionTop: number
  captionY: number | null
  top: number
  height: number
  y: (value: number) => number
  offAbove: OffBand | null
  offBelow: OffBand | null
  labels: LabelPlan
  /** Every valued bar of the panel's bar marks, in mark then period order. */
  bars: PlacedBar[]
  gaps: SlotText[]
  /** A signed bar drawn as the 2 px stub prints its value: the stub alone can't show the sign. */
  nearZero: NearZeroLabel[]
  /** The periods whose near-zero label did not fit (A13b); their values stay in the strip. */
  nearZeroDropped: string[]
}

export interface ChartLayout {
  view: ChartView
  width: number
  height: number
  gutter: number
  plotLeft: number
  plotRight: number
  slot: number
  barWidth: number
  /** Growth bars are narrower than the top-line bars above them, so the two panels read apart. */
  growthBarWidth: number
  x: (period: string) => number
  panels: PanelBox[]
  xTickY: number
  stripTop: number | null
  /** Each strip row's baseline, in the model's strip order; empty without a strip. */
  stripRowY: number[]
  /** A labelled panel found no label tier (A4): the card shows VALUES_DONT_FIT. */
  valuesDontFit: boolean
  /** The notes band's baseline: the band is reserved on every chart, so plots line up across a grid row. */
  notesY: number
}

/**
 * The left gutter and the narrowest slot. The gutter holds the widest tick label (G_L). An expanded view with a
 * value strip also fits its rows, so the strip is collision-free by construction as §3.10 says: every slot holds
 * its widest cell with 2 px each side, and the gutter reaches past the rows' short names, so the first cell
 * clears them.
 */
function frameOf(model: ChartModel, view: ChartView): { gutter: number; minSlot: number } {
  const chars = Math.max(0, ...model.panels.flatMap((panel) => panel.axis.ticks.map((tick) => [...panel.axis.format.tick(tick)].length)))
  const gutter = Math.max(36, Math.ceil(ADVANCE * chars) + 8)
  if (view !== 'expanded' || !model.strip.length) return { gutter, minSlot: MIN_SLOT }
  const cell = Math.max(0, ...model.strip.flatMap((row) => Object.values(row.cells).map(textWidth)))
  const label = Math.max(0, ...model.strip.map((row) => textWidth(row.short)))
  return { gutter: Math.max(gutter, Math.ceil(STRIP_LABEL_X + label)), minSlot: Math.max(MIN_SLOT, Math.ceil(cell + 4)) }
}

/** A7: the narrowest width at which every slot keeps its minimum; below it the SVG scrolls in its card. A labelled
 *  chart takes the narrowest whole-pixel width, at most LABELLED_MAX_SLOT a period, at which A4 finds a tier for every
 *  labelled panel, so a phone scrolls a little further rather than print no values; when none does, it keeps its
 *  minimum. The search steps a slot pixel at a time, then the pixel within the last step. */
export function minChartWidth(model: ChartModel, view: ChartView = 'card'): number {
  const { gutter, minSlot } = frameOf(model, view)
  const at = (slot: number) => gutter + RIGHT_PAD + slot * model.periods.length
  const fits = (width: number) => !plan(model, width, view).valuesDontFit
  if (!model.panels.some((panel) => panel.marks.some((mark) => mark.labelled)) || fits(at(minSlot))) return at(minSlot)
  for (let slot = minSlot + 1; slot <= LABELLED_MAX_SLOT; slot++) {
    if (!fits(at(slot))) continue
    let width = at(slot - 1) + 1
    while (!fits(width)) width++
    return width
  }
  return at(minSlot)
}

/** Off-scale rows: entries sorted by x take the lowest row where their box (glyph and value, padded 4 px
 *  each side) clears every box already in it, so neighbouring slots stack rather than collide. */
function planOffScale(panel: ModelPanel, side: 'above' | 'below', x: (period: string) => number, width: number): Omit<OffBand, 'top'> | null {
  const entries = panel.marks.flatMap((mark) => mark.kind !== 'line' ? [] : mark.points
    .filter((point) => point.offscale === side && point.value != null)
    .map((point) => ({
      period: point.period, seriesKey: mark.seriesKey, color: mark.color, x: x(point.period),
      text: panel.axis.format.value(point.value!, Math.abs(point.value!) >= 1000 ? 0 : 1),
    })))
    .sort((a, b) => a.x - b.x)
  if (!entries.length) return null
  const rows: { x0: number; x1: number }[][] = []
  const items: OffItem[] = entries.map((entry) => {
    const w = textWidth(entry.text) + OFF_GLYPH
    const left = Math.max(1, Math.min(width - w - 1, entry.x - w / 2))
    const box = { x0: left - 4, x1: left + w + 4 }
    let row = rows.findIndex((taken) => taken.every((other) => box.x1 <= other.x0 || box.x0 >= other.x1))
    if (row < 0) {
      rows.push([])
      row = rows.length - 1
    }
    rows[row].push(box)
    return { ...entry, left, row }
  })
  return { depth: rows.length, items }
}

type PanelFrame = Omit<PanelBox, 'labels' | 'bars' | 'gaps' | 'nearZero' | 'nearZeroDropped'>
type Bar = Omit<PlacedBar, 'label'>

const zeroOf = (box: PanelFrame) => box.y(Math.max(box.panel.axis.domain[0], Math.min(0, box.panel.axis.domain[1])))

/** A13, every bar (top line, growth, equity): the rect from the zero rule to the clamped value, at least
 *  2 px, on the value's side. */
function placeBars(box: PanelFrame, x: (period: string) => number, barWidth: number, growthBarWidth: number): Bar[] {
  const [d0, d1] = box.panel.axis.domain
  const zero = zeroOf(box)
  return box.panel.marks.flatMap((mark) => mark.kind === 'line' ? [] : mark.points.flatMap((point) => {
    if (point.value == null) return []
    const clamped = Math.max(d0, Math.min(d1, point.value))
    const length = Math.abs(box.y(clamped) - zero)
    const height = Math.max(2, length)
    const width = mark.kind === 'growth' ? growthBarWidth : barWidth
    return [{
      period: point.period, seriesKey: mark.seriesKey, value: point.value,
      x: x(point.period) - width / 2, y: point.value >= 0 ? zero - height : zero, width, height, zero,
      stub: length < 2, clipped: clamped !== point.value,
    }]
  }))
}

/** A bar label's baseline and its planned box: 3 px beyond the bar's end, 12 px tall. */
function labelAt(bar: Bar) {
  const top = bar.value >= 0 ? bar.y - 3 - 12 : bar.y + bar.height + 3
  return { top, baseline: bar.value >= 0 ? bar.y - 5 : bar.y + bar.height + 12 }
}

/** A3/A4: one decimal tier for the whole panel, the most precise whose labels stay inside the SVG and keep
 *  2 px from each other in both directions. Never thinned: a tier fits every label or none. */
function planLabels(mark: ModelMark, box: PanelFrame, bars: Bar[], width: number): LabelPlan {
  if (!mark.labelled) return { decimals: null }
  const format = box.panel.axis.format
  const tiers = format.kind === 'money' ? Array.from({ length: format.d0 + 1 }, (_, i) => format.d0 - i) : [1, 0]
  const own = bars.filter((bar) => bar.seriesKey === mark.seriesKey)
  for (const digits of tiers) {
    const boxes = own.map((bar) => {
      const w = textWidth(format.value(bar.value, digits))
      const centre = bar.x + bar.width / 2
      const { top } = labelAt(bar)
      return { x0: centre - w / 2, x1: centre + w / 2, y0: top, y1: top + 12 }
    })
    const inside = boxes.every((b) => b.x0 >= 0 && b.x1 <= width)
    const apart = boxes.every((a, i) => boxes.every((b, j) => j <= i || a.x1 + 2 <= b.x0 || b.x1 + 2 <= a.x0 || a.y1 + 2 <= b.y0 || b.y1 + 2 <= a.y0))
    if (inside && apart) return { decimals: digits }
  }
  return { decimals: null }
}

/** A13b: a non-zero signed bar whose true length is under 2 px is drawn as the 2 px stub on its sign's
 *  side, and prints its value to 2 significant figures in its own unit, on the side of the zero rule that
 *  has room. A label that would not fit its slot or would touch the previous one is left to the strip. */
function planNearZero(box: PanelFrame, bars: Bar[], slot: number): Pick<PanelBox, 'nearZero' | 'nearZeroDropped'> {
  const zero = zeroOf(box)
  const above = zero - box.top >= 14
  const signed = new Set(box.panel.marks.filter((mark) => mark.kind === 'signedBar').map((mark) => mark.seriesKey))
  const nearZero: NearZeroLabel[] = []
  const nearZeroDropped: string[] = []
  for (const bar of bars) {
    if (!signed.has(bar.seriesKey) || !bar.stub || bar.value === 0) continue
    const text = compactMoney(bar.value, box.panel.currency)
    const w = textWidth(text)
    const centre = bar.x + bar.width / 2
    const last = nearZero.at(-1)
    if (w > slot - 2 || (last && last.x + textWidth(last.text) / 2 + 2 > centre - w / 2)) nearZeroDropped.push(bar.period)
    else nearZero.push({ period: bar.period, x: centre, y: above ? zero - 5 : zero + 13, text })
  }
  return { nearZero, nearZeroDropped }
}

export function layoutChart(model: ChartModel, containerWidth: number, view: ChartView): ChartLayout {
  return plan(model, Math.max(containerWidth, minChartWidth(model, view)), view)
}

/** The whole plan at a given SVG width. */
function plan(model: ChartModel, width: number, view: ChartView): ChartLayout {
  const { gutter } = frameOf(model, view)
  const plotLeft = gutter
  const plotRight = width - RIGHT_PAD
  const slot = (plotRight - plotLeft) / Math.max(1, model.periods.length)
  const barWidth = Math.min(44, Math.round(0.64 * slot))
  const growthBarWidth = Math.max(4, Math.round(0.6 * barWidth))
  const index = new Map(model.periods.map((period, i) => [period.key, i]))
  const x = (period: string) => plotLeft + slot * ((index.get(period) ?? 0) + 0.5)
  const stacked = model.panels.length > 1
  const gap = view === 'expanded' ? 16 : 10
  const xAxisHeight = model.mode === 'quarterly' ? 32 : 20
  const stripHeight = view === 'expanded' && model.strip.length ? model.strip.length * STRIP_ROW + 6 : 0
  const height = HEIGHT[view] + stripHeight
  // Fixed bands per panel: caption, top pad (bar labels, or half a tick label), bottom pad, off-scale rows.
  const fixed = model.panels.map((panel) => {
    const offUp = planOffScale(panel, 'above', x, width)
    const offDown = planOffScale(panel, 'below', x, width)
    return {
      caption: stacked && panel.caption ? CAPTION : 0,
      padTop: panel.marks.some((mark) => mark.labelled) ? LABEL_PAD : TICK_PAD,
      // Labels sit below a negative bar's end, so a labelled panel with one keeps a label pad under it too.
      padBottom: panel.marks.some((mark) => mark.kind === 'growth' || (mark.labelled && mark.points.some((point) => (point.value ?? 0) < 0))) ? LABEL_PAD : TICK_PAD,
      offTop: offUp ? OFF_ROW * offUp.depth + 4 : 0,
      offBottom: offDown ? OFF_ROW * offDown.depth + 4 : 0,
      offUp, offDown,
    }
  })
  const topPad = stacked ? 4 : 8
  const fixedSum = topPad + fixed.reduce((sum, f) => sum + f.caption + f.padTop + f.padBottom + f.offTop + f.offBottom, 0)
    + (model.panels.length - 1) * gap + xAxisHeight + stripHeight + NOTES_ROW + BOTTOM
  const flex = Math.max(60, height - fixedSum)
  const weights = model.panels.reduce((sum, panel) => sum + panel.weight, 0)
  let cursor = topPad
  let assigned = 0
  const panels: PanelBox[] = model.panels.map((panel, i) => {
    const f = fixed[i]
    const regionTop = i === 0 ? 0 : cursor
    const captionY = f.caption ? cursor + 11 : null
    cursor += f.caption
    const offAbove = f.offUp ? { top: cursor, ...f.offUp } : null
    cursor += f.offTop + f.padTop
    const panelHeight = i === model.panels.length - 1 ? flex - assigned : Math.round((flex * panel.weight) / weights)
    assigned += panelHeight
    const top = cursor
    cursor += panelHeight + f.padBottom
    const offBelow = f.offDown ? { top: cursor, ...f.offDown } : null
    cursor += f.offBottom + (i < model.panels.length - 1 ? gap : 0)
    const frame: PanelFrame = { panel, regionTop, captionY, top, height: panelHeight, y: linear(panel.axis.domain, [top + panelHeight, top]), offAbove, offBelow }
    const placed = placeBars(frame, x, barWidth, growthBarWidth)
    const labelled = panel.marks.find((mark) => mark.labelled)
    const labels = labelled ? planLabels(labelled, frame, placed, width) : { decimals: null }
    const printed = new Set(panel.marks.filter((mark) => mark.labelled).map((mark) => mark.seriesKey))
    const bars = placed.map((bar) => ({
      ...bar,
      label: labels.decimals != null && printed.has(bar.seriesKey) ? { text: panel.axis.format.value(bar.value, labels.decimals), y: labelAt(bar).baseline } : null,
    }))
    const zero = zeroOf(frame)
    const gaps = panel.marks.flatMap((mark) => mark.kind === 'line' ? [] : mark.points
      .filter((point) => point.value == null)
      .map((point): SlotText => ({ period: point.period, text: point.nm ? 'n/m' : '—', x: x(point.period), y: zero - 3 })))
    return { ...frame, labels, bars, gaps, ...planNearZero(frame, placed, slot) }
  })
  const xTickY = cursor + 13
  cursor += xAxisHeight
  const stripTop = stripHeight ? cursor + 4 : null
  cursor += stripHeight
  const stripRowY = stripTop == null ? [] : model.strip.map((_, i) => stripTop + 12 + i * STRIP_ROW)
  const valuesDontFit = panels.some((box) => box.panel.marks.some((mark) => mark.labelled) && box.labels.decimals == null)
  return { view, width, height, gutter, plotLeft, plotRight, slot, barWidth, growthBarWidth, x, panels, xTickY, stripTop, stripRowY, valuesDontFit, notesY: cursor + 12 }
}

export interface PlacedGlyph extends NoteGlyph {
  period: string
  x: number
}

/** The notes band's glyphs, one text per glyph centred on its period's slot, so every renderer and the
 *  export place them identically and each letter can take its own ink. Glyphs sit 1.5 px apart, each as wide
 *  as its text: A5's (k − (n−1)/2) × (6.6 + 1.5) for one-letter glyphs, and no overlap for "aa". */
export function noteGlyphs(model: ChartModel, layout: ChartLayout): PlacedGlyph[] {
  if (!model.notesBand) return []
  return Object.entries(model.notesBand).flatMap(([period, glyphs]) => {
    const widths = glyphs.map((glyph) => textWidth(glyph.text))
    let left = layout.x(period) - (widths.reduce((sum, w) => sum + w, 0) + 1.5 * (glyphs.length - 1)) / 2
    return glyphs.map((glyph, i) => {
      const x = left + widths[i] / 2
      left += widths[i] + 1.5
      return { ...glyph, period, x }
    })
  })
}
