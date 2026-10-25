/**
 * The trend charts' per-period readout (docs/design/analysis-trend-charts-spec-2026-10.md §3.9, §3.13): what the
 * tooltip shows and the live status says for one period of one chart. The rows are the chart's marks in legend order
 * (§3.5: the top line then its YoY growth; debt, cash, then equity), each with its value at tooltip precision (§3.1),
 * its state text, whether this point is calculated, and its own note letter: a value's note, and for the growth row its
 * comparison note, so value and YoY concerns stay independent (DESIGN_SYSTEM.md §10). Pure and SSR-safe, like the
 * model it reads; a renderer prints these strings and computes none.
 */
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import type { DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { isCalculated, MONTHS, type ChartModel, type Marker, type ModelMark, type ModelPanel, type ModelPoint } from './model'
import { tooltipMoney } from './scale'

export interface ReadoutRow {
  seriesKey: string
  /** The legend's name ("Gross", "Long-term debt"), or the top line's and "YoY growth". */
  label: string
  /** The palette slot and swatch the legend gives the series. */
  color: number
  swatch: 'bar' | 'line'
  marker?: Marker
  /** The value at tooltip precision: 4 significant figures for an amount, 1 dp for a percent. Null with no value. */
  value: string | null
  /** The state of a slot with no value, or of an off-scale value; null for an ordinary value. */
  state: 'unavailable' | 'not-meaningful' | 'no-prior-year' | 'off-scale' | null
  /** This value is calculated (never on a growth row: every growth rate is a calculated comparison). */
  calculated: boolean
  /** This point's own note letter, or null; a review-kind note takes the review ink, as in the notes band. */
  note: string | null
  noteTone: 'review' | 'neutral'
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
   *  ("·", "—", "n/m", "B", "YoY", "Dec", U+2212). "FY2021, year ended December 31, 2021. Long-term debt: unavailable,
   *  data note b. Cash: $1.234 billion, calculated." */
  announcement: string
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2025-12-31" → "Dec 31, 2025" ("December 31, 2025" spoken), or null for a date it cannot read. No Date object, so no
 *  time zone moves the day. */
export function periodEndText(periodEnd: string | undefined, spoken = false): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(periodEnd ?? '')
  const month = match ? (spoken ? MONTH_NAMES : MONTHS)[Number(match[2]) - 1] : undefined
  return match && month ? `${month} ${Number(match[3])}, ${match[1]}` : null
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

/** "−$3.588M" → "minus $3.588 million", "+28.0%" → "plus 28.0%": a sign some readers drop at default settings, and a
 *  unit letter they spell out. */
const spokenValue = (value: string) => value
  .replace(/^−/, 'minus ')
  .replace(/^\+/, 'plus ')
  .replace(/(\d)([KMBT])$/, (_, digit: string, unit: string) => `${digit} ${UNITS[unit]}`)

function rowOf(mark: ModelMark, panel: ModelPanel, point: ModelPoint, dataset: AnalysisDataset, notes: DataNotesModel): ReadoutRow {
  const growth = mark.kind === 'growth'
  const series = dataset.series.find((candidate) => candidate.concept === mark.seriesKey.split(':')[0])
  const source = series?.points.find((candidate) => candidate.period === point.period)
  const format = panel.axis.format
  const value = point.value == null ? null : format.kind === 'money' ? tooltipMoney(point.value, panel.currency) : format.value(point.value, 1)
  const state: ReadoutRow['state'] = point.value != null
    ? point.offscale ? 'off-scale' : null
    : point.nm ? 'not-meaningful' : point.structural ? 'no-prior-year' : 'unavailable'
  // The band's rule (model.ts notesBandOf): a period the series has no point for is unavailable and carries that note.
  const note = (growth ? source && notes.noteForComparison(source, 'yoy') : notes.noteFor(source ?? { value: null })) ?? null
  const calculated = !growth && isCalculated(source)
  const figure = [value, state && STATE_TEXT[state].shown].filter(Boolean).join(' ')
  return {
    seriesKey: mark.seriesKey, label: mark.label, color: mark.color, swatch: mark.kind === 'line' ? 'line' : 'bar', marker: mark.marker,
    value, state, calculated, note: note?.letter ?? null, noteTone: note?.kind === 'review' ? 'review' : 'neutral', figure,
    text: [figure, calculated ? '· Calculated' : null, note ? `(${note.letter})` : null].filter(Boolean).join(' '),
  }
}

/** The table's own words for a note (DataNoteMark's dataNoteDescription): "data note b". */
const spoken = (row: ReadoutRow) => [
  `${row.seriesKey.endsWith(':yoy') ? 'Year-over-year growth' : SPOKEN_NAMES[row.seriesKey] ?? row.label}: ${row.value == null ? STATE_TEXT[row.state ?? 'unavailable'].spoken : spokenValue(row.value)}`,
  row.value != null && row.state ? STATE_TEXT[row.state].spoken : null,
  row.calculated ? 'calculated' : null,
  row.note ? `data note ${row.note}` : null,
].filter(Boolean).join(', ')

/** One readout per period of the chart, in the model's period order; none for a chart that does not apply. */
export function chartReadouts(model: ChartModel, dataset: AnalysisDataset, notes: DataNotesModel): PeriodReadout[] {
  if (model.unavailable) return []
  const ends = new Map(dataset.periods.map((period) => [period.key, period.period_end]))
  const span = dataset.mode === 'annual' ? 'year' : 'quarter'
  const marks = model.panels.flatMap((panel) => panel.marks.map((mark) => [mark, panel] as const))
  return model.periods.map(({ key }) => {
    const name = formatAnalysisPeriod(key)
    const end = periodEndText(ends.get(key))
    const endSpoken = periodEndText(ends.get(key), true)
    const rows = marks.flatMap(([mark, panel]) => {
      const point = mark.points.find((candidate) => candidate.period === key)
      return point ? [rowOf(mark, panel, point, dataset, notes)] : []
    })
    return {
      period: key,
      header: end ? `${name} · ${span} ended ${end}` : name,
      rows,
      announcement: `${[endSpoken ? `${name}, ${span} ended ${endSpoken}` : name, ...rows.map(spoken)].join('. ')}.`,
    }
  })
}
