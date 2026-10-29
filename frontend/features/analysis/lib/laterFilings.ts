import { fmtCount, formatLocalDate } from '@/lib/format'
import type { AnalysisDataset, AnalysisPoint, AnalysisSeries, FirstReported, GrowthValue } from '@/features/analysis/api/analysis-api'
import { compactFigure, exactFigure } from '@/features/analysis/lib/figureDisplay'
import { formatGrowth } from '@/features/analysis/lib/growth'
import type { FactInput, FactProvenance } from '@/features/analysis/lib/provenance'

/**
 * The page's reader of the later-filing evidence (MPA WP5a; docs/mpa-improvements/coherence.md §1.6 items 2-5, D-061).
 * Where a later filing reports a value other than the one a fiscal year's own annual report gave, the point shows the
 * later one and carries the own report's as `first_reported`, an input of a calculated figure likewise; a YoY whose two
 * years sit on different bases reads "nm" and carries `yoy_first_reported`. None of it is a data note: only the exact
 * sign flip or factor of 1,000ⁿ is also one (the producer's `source_conflict`), which the notes model reads from the
 * point's provenance as it reads any note. Every field is optional and a dataset without them is read exactly as
 * before; the reader lands before its producer, so a deployed page never misstates a cause (WP5a-F1).
 *
 * Annual runs alone carry it. WP5b (#1682) stores fiscal-year history rows only, and the producer (WP5a-B) sends
 * evidence in annual mode only (D5), so a quarterly run's evidence, and a QoQ's anywhere, refuses the dataset until a
 * later pull request adds quarterly evidence together with its reader.
 */

/** The decoder's own rejection of a payload, as DataNotesRejection is the notes decoder's: a caller catches this class
 *  alone, and a TypeError from inside the decoder is a defect. */
export class LaterFilingsRejection extends TypeError {
  constructor(detail: string) {
    super(`Invalid later-filing evidence: ${detail}`)
    this.name = 'LaterFilingsRejection'
  }
}

function invalid(detail: string): never {
  throw new LaterFilingsRejection(detail)
}

const present = (value: unknown) => value !== undefined && value !== null

function finite(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) invalid(`${field} must be a finite number`)
  return value
}

function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.length) invalid(`${field} must be a nonempty string`)
  return value
}

/** Null, absent, or a calendar day as the producer writes it (YYYY-MM-DD) that exists. */
function day(value: unknown, field: string) {
  if (!present(value)) return
  const [year, month, date] = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').map(Number) : []
  const calendar = year ? new Date(Date.UTC(year, month - 1, date)) : null
  if (!calendar || calendar.getUTCFullYear() !== year || calendar.getUTCMonth() !== month - 1 || calendar.getUTCDate() !== date) {
    invalid(`${field} must be a YYYY-MM-DD day or null`)
  }
}

/** The factor of 1,000ⁿ (n from -3 to 3, never 0) that takes `own` to `shown`, or null where none does exactly. */
export function scaleSteps(own: number, shown: number): number | null {
  if (own === 0 || shown === 0 || Math.sign(own) !== Math.sign(shown)) return null
  const steps = Math.round(Math.log10(Math.abs(shown / own)) / 3)
  if (steps === 0 || Math.abs(steps) > 3) return null
  const expected = own * 1000 ** steps
  return Math.abs(shown - expected) <= Math.abs(expected) * 1e-9 ? steps : null
}

/** One `first_reported` against the figure it sits on: the figure's value, unit and accession. */
function checkFirstReported(raw: unknown, figure: { value?: unknown; unit?: unknown; accession?: unknown }, where: string) {
  if (typeof raw !== 'object' || Array.isArray(raw)) invalid(`${where}.first_reported must be an object`)
  const first = raw as Record<string, unknown>
  const shown = finite(figure.value, `${where}.value beside first_reported`)
  const value = finite(first.value, `${where}.first_reported.value`)
  // Evidence says a later filing reports a different value: an equal one is no evidence.
  if (value === shown) invalid(`${where}.first_reported.value equals the value shown`)
  if (text(first.unit, `${where}.first_reported.unit`) !== figure.unit) invalid(`${where}.first_reported.unit is not the figure's unit`)
  const accession = text(first.accession, `${where}.first_reported.accession`)
  if (typeof figure.accession === 'string' && accession === figure.accession) invalid(`${where}.first_reported.accession is the shown filing's`)
  if (present(first.form)) text(first.form, `${where}.first_reported.form`)
  if (present(first.source_url) && typeof first.source_url !== 'string') invalid(`${where}.first_reported.source_url must be a string or null`)
  day(first.filed_at, `${where}.first_reported.filed_at`)
  day(first.later_filed_at, `${where}.first_reported.later_filed_at`)
  const disagreement = first.disagreement
  if (present(disagreement) && disagreement !== 'opposite_sign' && disagreement !== 'scale') invalid(`${where}.first_reported.disagreement is unsupported`)
  // The finding the dialog states is built from the two values, so it must be what they show.
  if (disagreement === 'opposite_sign' && shown !== -value) invalid(`${where}.first_reported is no exact sign flip`)
  if (disagreement === 'scale' && scaleSteps(value, shown) === null) invalid(`${where}.first_reported is no exact factor of 1,000`)
}

function annualOnly(annual: boolean, field: string) {
  if (!annual) invalid(`${field}: only an annual run carries later-filing evidence (D5)`)
}

function checkInputs(provenance: FactProvenance | null | undefined, annual: boolean, where: string) {
  if (!provenance || !Array.isArray(provenance.inputs)) return
  provenance.inputs.forEach((input: FactInput, index) => {
    const at = `${where}.inputs[${index}]`
    if (present(input?.first_reported)) {
      annualOnly(annual, `${at}.first_reported`)
      checkFirstReported(input.first_reported, input, at)
    }
    checkInputs(input?.provenance, annual, at)
  })
}

/** The fiscal year before `key`: FY2020 → FY2019. */
const yearBefore = (key: string) => key.replace(/^FY(\d{4})$/, (_, year) => `FY${Number(year) - 1}`)

function checkPoint(point: AnalysisPoint, series: AnalysisSeries, byPeriod: ReadonlyMap<string, AnalysisPoint>, annual: boolean, where: string) {
  if (!point || typeof point !== 'object') return
  if (present(point.first_reported)) {
    annualOnly(annual, `${where}.first_reported`)
    // Reported figures only: a calculated figure's evidence sits on its inputs (item 5).
    if (point.provenance?.method === 'calculated') invalid(`${where}.first_reported sits on a calculated figure, whose evidence belongs on its inputs`)
    checkFirstReported(point.first_reported, { value: point.value, unit: point.unit ?? series.unit, accession: point.accession }, where)
  }
  // A QoQ never carries it: a quarterly run has no evidence yet, and an annual run no QoQ.
  if ((point as { qoq_first_reported?: unknown }).qoq_first_reported !== undefined) invalid(`${where}.qoq_first_reported: no QoQ carries later-filing evidence (D5)`)
  const first = point.yoy_first_reported
  if (first !== undefined) {
    annualOnly(annual, `${where}.yoy_first_reported`)
    // Present only where the YoY reads n/m across a change of basis: that is how the page tells this n/m's cause from
    // a sign change's.
    if (point.yoy !== 'nm') invalid(`${where}.yoy_first_reported sits beside a yoy that is not n/m`)
    if (first !== null && first !== 'nm') finite(first, `${where}.yoy_first_reported`)
    // Across a sign or scale finding on either year, one of the two readings rests on the slip and the page cannot tell
    // which, so the growth as first reported is n/m there too (chief design on #1776).
    const findings = [point, byPeriod.get(yearBefore(point.period))].filter((year) => present(year?.first_reported?.disagreement))
    if (findings.length && first !== 'nm') invalid(`${where}.yoy_first_reported must be n/m across a sign or scale finding`)
  }
  checkInputs(point.provenance, annual, where)
  checkInputs(point.yoy_provenance, annual, `${where}.yoy_provenance`)
  checkInputs(point.qoq_provenance, annual, `${where}.qoq_provenance`)
}

/** Checks every later-filing field the dataset carries (rule 9, at the boundary) and returns the dataset as sent. A
 *  field the page would print wrong refuses the dataset, as a broken data notes envelope does: any of them in a run
 *  that is not annual, and a `qoq_first_reported` anywhere; a `first_reported` on a calculated figure, or one whose
 *  value is not finite or equals the shown one, whose unit is not the figure's, whose accession is the shown filing's,
 *  whose days are not days, or whose `disagreement` the two values do not show; a `yoy_first_reported` beside a YoY
 *  that is not n/m, or other than n/m across a sign or scale finding on either year. A dataset that carries none of
 *  them is not touched. */
export function decodeLaterFilings<T extends Pick<AnalysisDataset, 'mode' | 'series'>>(dataset: T): T {
  if (!Array.isArray(dataset?.series)) return dataset
  const annual = dataset.mode === 'annual'
  dataset.series.forEach((series, seriesIndex) => {
    if (!Array.isArray(series?.points)) return
    const where = `series[${seriesIndex}]`
    const byPeriod = new Map(series.points.filter((point) => point && typeof point === 'object').map((point) => [point.period, point]))
    series.points.forEach((point, index) => checkPoint(point, series, byPeriod, annual, `${where}.points[${index}]`))
    checkInputs(series.cagr_provenance, annual, `${where}.cagr_provenance`)
    checkInputs(series.window_pp_provenance, annual, `${where}.window_pp_provenance`)
  })
  return dataset
}

/** Whether a point's YoY reads n/m because a later filing reports a different value for one or both of its years, not
 *  because its values change sign. */
export const basisChanged = (point: Pick<AnalysisPoint, 'yoy' | 'yoy_first_reported'> | null | undefined): boolean =>
  point?.yoy === 'nm' && point.yoy_first_reported !== undefined

/** What the evidence dialog's YoY comparison says of a basis n/m (D12): nothing (undefined) unless its basis changed,
 *  else the growth as first reported in the comparison's own form ("+14.3%", "+16.0pp", "n/m"), or null where the own
 *  reports give none. */
export function comparisonLaterFiling(point: Pick<AnalysisPoint, 'yoy' | 'yoy_first_reported'>, isPercent: boolean): { asFirstReported: string | null } | undefined {
  if (!basisChanged(point)) return undefined
  const first: GrowthValue | null | undefined = point.yoy_first_reported
  return { asFirstReported: formatGrowth(first, isPercent).text || null }
}

type Figure = { concept?: string; unit?: string | null }

/** The two values as the sentence prints them: compact, with more decimals where the compact form prints them alike
 *  (a 0.24% gap reads "$15.16B" and "$15.20B", never "$15.2B" twice), and as stored where none tells them apart. */
export function distinctFigures(own: number, shown: number, figure: Figure): [string, string] {
  for (const digits of [undefined, 2, 3, 4]) {
    const pair: [string, string] = [compactFigure(own, figure, digits), compactFigure(shown, figure, digits)]
    if (pair[0] !== pair[1]) return pair
  }
  return [exactFigure(own, figure), exactFigure(shown, figure)]
}

/** A filing's form and filed day as the evidence names them, "10-K, filed 7 Feb 2019", each part left out where the
 *  payload has none: never an invented form or day. */
export function filingParts(form: string | null | undefined, filedAt: string | null | undefined): string {
  const filed = formatLocalDate(filedAt, 'd MMM yyyy')
  return [form, filed && `filed ${filed}`].filter(Boolean).join(', ')
}

/** The evidence sentence (D11), for a reported figure and for a calculated figure's input alike: the own report's
 *  value, then the later filing's, the one shown. */
export function firstReportedSentence(first: FirstReported, shown: number, figure: Figure): string {
  const [own, later] = distinctFigures(first.value, shown, figure)
  const ownFiling = filingParts(first.form, first.filed_at)
  const laterFiled = formatLocalDate(first.later_filed_at, 'd MMM yyyy')
  return `First reported as ${own} in its own annual report${ownFiling && ` (${ownFiling})`}. A later filing${laterFiled && ` (filed ${laterFiled})`} reports ${later}, shown here.`
}

/** What the exact comparison found, in words built from the two values (D2): the opposite sign, or the factor of
 *  1,000ⁿ and which way it runs. Null for any other difference, which says nothing more than the evidence sentence. */
export function disagreementSentence(first: FirstReported, shown: number): string | null {
  if (first.disagreement === 'opposite_sign') return 'A later filing reports the opposite sign.'
  const steps = first.disagreement === 'scale' ? scaleSteps(first.value, shown) : null
  if (steps === null) return null
  return `A later filing reports a value ${fmtCount(1000 ** Math.abs(steps))} times ${steps > 0 ? 'larger' : 'smaller'} than the year’s own annual report.`
}

export interface LaterFilingRef { concept: string; label: string; period: string }
export interface LaterFilingPlaces {
  /** The figures that carry their own first-reported value. They are reported figures, since the decoder refuses the
   *  field on a calculated one, whose evidence sits on its inputs; each opens a dialog that gives both filings. */
  values: LaterFilingRef[]
  /** The YoY changes that read n/m across a change of basis. */
  comparisons: LaterFilingRef[]
}

/** Where the run carries later-filing evidence, for the data notes' line (D8): over the window's periods only, in series
 *  order, then period order. Only an annual run can carry it (decodeLaterFilings), so a quarterly run has none. It reads
 *  the points, not the notes envelope, so the line moves no data notes version. The shared fixture
 *  backend/tests/fixtures/analysis_later_filings.json holds these places, which the backend's twin computes for the
 *  exports' line (WP5a-X) from the same cases. */
export function laterFilingPlaces(dataset: Pick<AnalysisDataset, 'periods' | 'series'>): LaterFilingPlaces {
  const places: LaterFilingPlaces = { values: [], comparisons: [] }
  for (const series of dataset.series) {
    const points = new Map(series.points.map((point) => [point.period, point]))
    for (const { key } of dataset.periods) {
      const point = points.get(key)
      if (!point) continue
      const ref = { concept: series.concept, label: series.label, period: key }
      if (point.first_reported) places.values.push(ref)
      if (basisChanged(point)) places.comparisons.push(ref)
    }
  }
  return places
}
