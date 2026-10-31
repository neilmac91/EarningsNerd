/**
 * A one-metric bar chart on the trend charts' engine, built from a plain definition rather than an analysis dataset
 * (E195 (D): the filing page's Financial trends, drawn as /analysis draws its charts). One bar mark in chart-1 over the
 * categories its caller names, every value printed on its bar (A4), on one value axis: an amount in its filer's own
 * currency (a per-share amount too, its tooltip in cents), a percent or a ratio. A category without a value keeps its
 * slot and prints "—", as the analysis charts' bars do. A category can be a context bar (E251): one the chart sets beside
 * the bars it is about, such as a sector's other companies, in the context ink. The model is theirs, so layout.ts,
 * readout.ts and the renderer take it as it is, and tests/unit/chart-engine.spec.ts holds it to the same model checks
 * (docs/design/analysis-trend-charts-spec-2026-10.md §0.5). Pure and SSR-safe.
 */
import { currencySymbol } from '@/lib/format'
import { AXIS_CAPS, percentPanel, type ChartModel, type ChartPeriod, type ChartReading, type Footnote, type ModelMark, type ModelPanel } from './model'
import { valueAxis } from './scale'

/** One bar's slot. */
export interface BarCategory {
  /** Unique in its chart: the layout places a bar, and the readout reads it, by its key. */
  key: string
  /** The x tick, one line ("2025"). */
  tick: string
  /** The category's whole name ("FY2025"), the readout's header where its describer names none. */
  long: string
  /** A context bar (E251): one the chart sets beside the bars it is about, such as a sector's other companies. It paints
   *  the context ink, never a series colour, at the growth bars' narrower width, the cue colour alone cannot give a
   *  colour-blind reader (layout.ts). Its mark stays chart-1, so M9's order is the series' own. */
  context?: true
  /** The chart's run breaks before this category (E258): categories it leaves out stand between it and the one before,
   *  so the layout sets half a slot of empty plot before its slot (layout.ts `SEAM`), and even spacing never reads as an
   *  unbroken run. A ranked company chart's subject drawn after the top companies, past ones it leaves out. Never on the
   *  first category, before which there is no run to break. */
  gapBefore?: true
}

/** The value axis. A money axis takes its series' XBRL unit, whose currency the amounts carry: "USD", "CNY", or a currency
 *  a share ("USD/shares"). A percent's values are percentage points already (25.3 for 25.3%). */
export type BarAxis = { kind: 'money'; unit: string } | { kind: 'percent' } | { kind: 'ratio' }

export interface BarChartDef {
  /** The model's id; nothing reads it. */
  id: string
  /** The chart's name, as its plot announces it: "{title} chart", "{title} chart values". */
  title: string
  subtitle?: string
  categories: BarCategory[]
  /** The one series: its key, its name, and a value or null (withheld) for each category, in the categories' order. */
  series: { key: string; label: string; values: (number | null)[] }
  axis: BarAxis
  footnotes?: Footnote[]
  /** Set when the chart does not apply: one sentence, said at the card's height in place of a plot. */
  unavailable?: string | null
  /** The category the chart starts at, by key (E251; a ranked company chart's subject): its values stop starts there, and
   *  a plot that overflows opens with its column in view. Unset, the last category. */
  start?: string
  /** What the plot calls its categories (E251; a ranked company chart's companies): its scroll region's name and the
   *  status a step past either end says. Unset, its periods. */
  reading?: ChartReading
}

/** A1's interval cap: the top line's, the one panel of labelled bars on /analysis. */
const BAR_CAP = AXIS_CAPS.topline
const PANEL = 'bars'
/** The line a chart with a bar A3 clipped carries, as the top line's growth bars do. */
export const BROKEN_BARS: Footnote = { mark: '', text: 'Bars beyond the axis are broken; their printed value is the true value.' }

/** The currency an XBRL unit's amounts carry (lessons/frontend-xbrl-amounts-carry-their-own-currency.md): "CNY" is CNY,
 *  "USD/shares" is USD a share, and a unit that names no ISO 4217 currency ("pure", "shares") has none, so its amounts
 *  print with no sign, never a default dollar. */
export function unitCurrency(unit: string): { currency: string | null; perShare: boolean } {
  const [code, per] = unit.split('/')
  return { currency: currencySymbol(code) ? code : null, perShare: per === 'shares' }
}

function panelOf(axis: BarAxis, mark: ModelMark): ModelPanel {
  // A percent axis clips as /analysis's do (A3): every bar prints its value, so a bar broken at the axis still says its
  // true value. Bars that printed none would have to pass every value to valueAxis instead (scale.ts).
  if (axis.kind === 'percent') return percentPanel(PANEL, null, 1, BAR_CAP, [mark], false)
  const values = mark.points.flatMap((point) => (point.value == null ? [] : [point.value]))
  const { currency, perShare } = axis.kind === 'money' ? unitCurrency(axis.unit) : { currency: null, perShare: false }
  return { id: PANEL, caption: null, weight: 1, nmax: BAR_CAP, marks: [mark], currency, axis: valueAxis(values, BAR_CAP, axis.kind, currency, perShare) }
}

export function buildBarChart(def: BarChartDef): ChartModel {
  const seen = new Set<string>()
  for (const { key } of def.categories) {
    // The layout would draw a second bar with the key over the first (layout.ts x()), and the readout read it twice.
    if (seen.has(key)) throw new Error(`buildBarChart ${def.id}: the category key "${key}" appears twice; each bar needs a slot of its own`)
    seen.add(key)
  }
  if (def.series.values.length !== def.categories.length) {
    throw new Error(`buildBarChart ${def.id}: ${def.series.values.length} values for ${def.categories.length} categories`)
  }
  // A start that names no category would leave the chart opening where its caller did not ask.
  if (def.start != null && !seen.has(def.start)) throw new Error(`buildBarChart ${def.id}: the start "${def.start}" names no category`)
  // A gap before the first bar would break no run, and would only push the plot's first slot off its gutter.
  if (def.categories[0]?.gapBefore) throw new Error(`buildBarChart ${def.id}: a gap before the first category "${def.categories[0].key}" breaks no run`)
  // One-line ticks, so the layout's one-line x axis: 'annual' is all layout.ts reads `mode` for. No legend (the card names
  // its one series), no notes band, and no value strip, since every value prints on its bar.
  const periods = def.categories.map(({ key, tick, long, gapBefore }): ChartPeriod => ({ key, tick: [tick], long, ...(gapBefore ? { gapBefore } : {}) }))
  const frame = {
    id: def.id, title: def.title, subtitle: def.subtitle ?? '', mode: 'annual' as const, periods, legend: [], notesBand: null, strip: [],
    ...(def.start != null ? { start: def.start } : {}),
    ...(def.reading ? { reading: def.reading } : {}),
  }
  if (def.unavailable) return { ...frame, panels: [], footnotes: [], unavailable: def.unavailable }
  // chart-1 whatever the metric: one series, so the first slot of A8's order.
  const mark: ModelMark = {
    kind: 'bar', seriesKey: def.series.key, label: def.series.label, color: 0, labelled: true,
    points: def.categories.map(({ key, context }, i) => ({ period: key, value: def.series.values[i], ...(context ? { context } : {}) })),
  }
  const panel = panelOf(def.axis, mark)
  return {
    ...frame, panels: [panel], unavailable: null,
    footnotes: [...(def.footnotes ?? []), ...(mark.points.some((point) => point.offscale) ? [BROKEN_BARS] : [])],
  }
}
