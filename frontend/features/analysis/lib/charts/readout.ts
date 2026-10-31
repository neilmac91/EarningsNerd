/**
 * The trend charts' per-period readout (docs/design/analysis-trend-charts-spec-2026-10.md §3.9, §3.13): what the
 * tooltip shows and the values stop's value text says for one period of one chart. The rows are the chart's marks in
 * legend order (§3.5: the top line then its YoY growth; debt, cash, then equity), each with its value at tooltip
 * precision (§3.1), its state text, whether this point is calculated, and its own note letter: a value's note, and for
 * the growth row its comparison note, so value and YoY concerns stay independent (DESIGN_SYSTEM.md §10). Pure and
 * SSR-safe, like the model it reads; a renderer prints these strings and computes none.
 *
 * `readouts` reads any model (E195 (D)): what the model does not hold, how a period is named and what is known of each
 * value, a describer tells it. `chartReadouts` is the analysis charts' describer, over their dataset and data notes.
 */
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { markedNote, type DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { isCalculated, MONTHS, type ChartModel, type ChartPeriod, type Marker, type ModelMark, type ModelPanel, type ModelPoint } from './model'

export interface ReadoutRow {
  seriesKey: string
  /** The legend's name ("Gross", "Long-term debt"), or the top line's and "YoY growth". */
  label: string
  /** The palette slot and swatch the legend gives the series. */
  color: number
  /** A context bar's row (barChart.ts, E251): its swatch takes the context ink, the hovered bar's own paint (E236). */
  context?: true
  swatch: 'bar' | 'line'
  marker?: Marker
  /** The value at tooltip precision: 4 significant figures for an amount, 1 dp for a percent. Null with no value. */
  value: string | null
  /** The state of a slot with no value, or of an off-scale value; null for an ordinary value. */
  state: 'unavailable' | 'not-meaningful' | 'no-prior-year' | 'off-scale' | null
  /** This value is calculated (never on a growth row: every growth rate is a calculated comparison). */
  calculated: boolean
  /** This point's own note letter where its note questions the number (D-061, `markedNote`), or null, as in the
   *  notes band. */
  note: string | null
  /** The value and its state as the tooltip prints them: "$14.34B", "Unavailable", "+581.9% (off scale)". */
  figure: string
  /** The whole row after the name: the figure, then " · Calculated" and " (a)" where they apply. */
  text: string
}

export interface PeriodReadout {
  period: string
  /** "FY2025 · year ended Dec 31, 2025" or "Q2 2026 · quarter ended Jun 30, 2026". */
  header: string
  rows: ReadoutRow[]
  /** The period as a screen reader says it, the values stop's value text: no glyph or abbreviation a reader garbles
   *  ("·", "—", "n/m", "B", "YoY", "Dec", U+2212). "FY2021, year ended December 31, 2021. Long-term debt: unavailable.
   *  Cash: $1.234 billion, calculated, data note a." */
  announcement: string
}

/** What a readout needs that its model does not hold. Each part is optional: by default a period's header is its long
 *  name, no value is calculated, none carries a note, and a series is spoken by its label. */
export interface ReadoutDescriber {
  /** A period's header as the tooltip prints it and as the values stop says it. */
  header?: (period: ChartPeriod) => { shown: string; spoken: string }
  /** Whether a mark's value in a period is calculated; a value that is not there never is. */
  calculated?: (mark: ModelMark, period: string) => boolean
  /** A mark's note letter in a period, where its note questions the number (D-061), or null. */
  note?: (mark: ModelMark, period: string) => string | null
  /** A series' name as a screen reader says it, where its label abbreviates it. */
  spokenName?: (mark: ModelMark) => string
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2025-12-31" → "Dec 31, 2025" ("December 31, 2025" spoken), or null for a date it cannot read. No Date object, so no
 *  time zone moves the day. */
export function periodEndText(periodEnd: string | null | undefined, spoken = false): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(periodEnd ?? '')
  const month = match ? (spoken ? MONTH_NAMES : MONTHS)[Number(match[2]) - 1] : undefined
  return match && month ? `${month} ${Number(match[3])}, ${match[1]}` : null
}

/** A period's header and its spoken form: "FY2025 · year ended Dec 31, 2025" and "FY2025, year ended December 31, 2025",
 *  or the name alone without an end date it can read. */
export function periodHeader(name: string, span: 'year' | 'quarter', periodEnd: string | null | undefined): { shown: string; spoken: string } {
  const end = periodEndText(periodEnd)
  const endSpoken = periodEndText(periodEnd, true)
  return { shown: end ? `${name} · ${span} ended ${end}` : name, spoken: endSpoken ? `${name}, ${span} ended ${endSpoken}` : name }
}

const STATE_TEXT: Record<NonNullable<ReadoutRow['state']>, { shown: string; spoken: string }> = {
  'unavailable': { shown: 'Unavailable', spoken: 'unavailable' },
  'not-meaningful': { shown: 'n/m · not meaningful', spoken: 'not meaningful' },
  'no-prior-year': { shown: 'No prior-year period in this window', spoken: 'not available, no prior-year period in this window' },
  'off-scale': { shown: '(off scale)', spoken: 'off scale' },
}

/** A series' name spoken in full where the legend abbreviates it, or names a margin by its kind alone. */
const SPOKEN_NAMES: Record<string, string> = {
  gross_margin: 'Gross margin',
  operating_margin: 'Operating margin',
  net_margin: 'Net margin',
  operating_cash_flow: 'Operating cash flow',
}
const UNITS: Record<string, string> = { K: 'thousand', M: 'million', B: 'billion', T: 'trillion' }

/** "−$3.588M" → "minus $3.588 million", "+28.0%" → "plus 28.0%", "0.87×" → "0.87 times": a sign some readers drop at
 *  default settings, and a unit letter or sign they spell out. */
const spokenValue = (value: string) => value
  .replace(/^−/, 'minus ')
  .replace(/^\+/, 'plus ')
  .replace(/(\d)([KMBT])$/, (_, digit: string, unit: string) => `${digit} ${UNITS[unit]}`)
  .replace(/(\d)×$/, '$1 times')

function rowOf(mark: ModelMark, panel: ModelPanel, point: ModelPoint, describer: ReadoutDescriber): ReadoutRow {
  const value = point.value == null ? null : panel.axis.format.tip(point.value)
  const state: ReadoutRow['state'] = point.value != null
    ? point.offscale ? 'off-scale' : null
    : point.nm ? 'not-meaningful' : point.structural ? 'no-prior-year' : 'unavailable'
  const note = describer.note?.(mark, point.period) ?? null
  const calculated = point.value != null && (describer.calculated?.(mark, point.period) ?? false)
  const figure = [value, state && STATE_TEXT[state].shown].filter(Boolean).join(' ')
  return {
    seriesKey: mark.seriesKey, label: mark.label, color: mark.color, ...(point.context ? { context: point.context } : {}),
    swatch: mark.kind === 'line' ? 'line' : 'bar', marker: mark.marker, value, state, calculated, note, figure,
    text: [figure, calculated ? '· Calculated' : null, note ? `(${note})` : null].filter(Boolean).join(' '),
  }
}

/** The table's own words for a note (DataNoteMark's dataNoteDescription): "data note b". */
const spoken = (row: ReadoutRow, name: string) => [
  `${name}: ${row.value == null ? STATE_TEXT[row.state ?? 'unavailable'].spoken : spokenValue(row.value)}`,
  row.value != null && row.state ? STATE_TEXT[row.state].spoken : null,
  row.calculated ? 'calculated' : null,
  row.note ? `data note ${row.note}` : null,
].filter(Boolean).join(', ')

/** One readout per period of any chart, in the model's period order; none for a chart that does not apply. */
export function readouts(model: ChartModel, describer: ReadoutDescriber = {}): PeriodReadout[] {
  if (model.unavailable) return []
  const marks = model.panels.flatMap((panel) => panel.marks.map((mark) => [mark, panel] as const))
  return model.periods.map((period) => {
    const header = describer.header?.(period) ?? { shown: period.long, spoken: period.long }
    const rows = marks.flatMap(([mark, panel]) => {
      const point = mark.points.find((candidate) => candidate.period === period.key)
      return point ? [{ row: rowOf(mark, panel, point, describer), name: describer.spokenName?.(mark) ?? mark.label }] : []
    })
    return {
      period: period.key,
      header: header.shown,
      rows: rows.map(({ row }) => row),
      announcement: `${[header.spoken, ...rows.map(({ row, name }) => spoken(row, name))].join('. ')}.`,
    }
  })
}

/** The analysis charts' readouts: each period named as the app prints it with its end date, a value calculated and noted
 *  as its dataset point is, and a series spoken by its full name. */
export function chartReadouts(model: ChartModel, dataset: AnalysisDataset, notes: DataNotesModel): PeriodReadout[] {
  const ends = new Map(dataset.periods.map((period) => [period.key, period.period_end]))
  const span = dataset.mode === 'annual' ? 'year' : 'quarter'
  const sourceOf = (mark: ModelMark, period: string) => dataset.series
    .find((candidate) => candidate.concept === mark.seriesKey.split(':')[0])?.points.find((candidate) => candidate.period === period)
  return readouts(model, {
    header: (period) => periodHeader(formatAnalysisPeriod(period.key), span, ends.get(period.key)),
    // Every growth rate is a calculated comparison, so a growth row never says so.
    calculated: (mark, period) => mark.kind !== 'growth' && isCalculated(sourceOf(mark, period)),
    // The band's rule (model.ts notesBandOf): only a note that questions the number gives a letter.
    note: (mark, period) => {
      const source = sourceOf(mark, period)
      return markedNote(mark.kind === 'growth' ? source && notes.noteForComparison(source, 'yoy') : notes.noteFor(source ?? { value: null }))?.letter ?? null
    },
    spokenName: (mark) => (mark.seriesKey.endsWith(':yoy') ? 'Year-over-year growth' : SPOKEN_NAMES[mark.seriesKey] ?? mark.label),
  })
}
