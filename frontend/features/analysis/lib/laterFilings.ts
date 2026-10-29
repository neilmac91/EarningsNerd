import type { AnalysisDataset, AnalysisPoint, AnalysisSeries, FirstReported, GrowthValue } from '@/features/analysis/api/analysis-api'
import type { FactInput, FactProvenance } from '@/features/analysis/lib/provenance'

/**
 * The page's reader of the later-filing evidence (MPA WP5a; docs/mpa-improvements/coherence.md §1.6 items 2-5, D-061).
 * Where a later filing reports a value other than the one a fiscal year's own annual report gave, the point shows the
 * later one and carries the own report's as `first_reported`, an input of a calculated figure likewise; a comparison
 * whose two periods sit on different bases reads "nm" and carries `{basis}_first_reported`. None of it is a data note:
 * only the exact sign flip or factor of 1,000ⁿ is also one (the producer's `source_conflict`), which the notes model
 * reads from the point's provenance as it reads any note. Every field is optional and a dataset without them is read
 * exactly as before; the reader lands before its producer, so a deployed page never misstates a cause (WP5a-F1).
 */

/** The bases a point's comparison can carry evidence on. A window's (CAGR, its percentage-point change) has none yet. */
export type LaterFilingBasis = 'yoy' | 'qoq'
const BASES: readonly LaterFilingBasis[] = ['yoy', 'qoq']

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

function checkInputs(provenance: FactProvenance | null | undefined, where: string) {
  if (!provenance || !Array.isArray(provenance.inputs)) return
  provenance.inputs.forEach((input: FactInput, index) => {
    const at = `${where}.inputs[${index}]`
    if (present(input?.first_reported)) checkFirstReported(input.first_reported, input, at)
    checkInputs(input?.provenance, at)
  })
}

function checkPoint(point: AnalysisPoint, series: AnalysisSeries, where: string) {
  if (!point || typeof point !== 'object') return
  if (present(point.first_reported)) {
    checkFirstReported(point.first_reported, { value: point.value, unit: point.unit ?? series.unit, accession: point.accession }, where)
  }
  for (const basis of BASES) {
    const first = point[`${basis}_first_reported`]
    if (first === undefined) continue
    // Present only where the comparison reads n/m across a change of basis: that is how the page tells this n/m's
    // cause from a sign change's.
    if (point[basis] !== 'nm') invalid(`${where}.${basis}_first_reported sits beside a ${basis} that is not n/m`)
    if (first !== null && first !== 'nm') finite(first, `${where}.${basis}_first_reported`)
  }
  checkInputs(point.provenance, where)
  checkInputs(point.yoy_provenance, `${where}.yoy_provenance`)
  checkInputs(point.qoq_provenance, `${where}.qoq_provenance`)
}

/** Checks every later-filing field the dataset carries (rule 9, at the boundary) and returns the dataset as sent. A
 *  field the page would print wrong refuses the dataset, as a broken data notes envelope does: a `first_reported` whose
 *  value is not finite or equals the shown one, whose unit is not the figure's, whose accession is the shown filing's,
 *  whose days are not days, or whose `disagreement` the two values do not show; a `{basis}_first_reported` beside a
 *  comparison that is not n/m. A dataset that carries none of them is not touched. */
export function decodeLaterFilings<T extends Pick<AnalysisDataset, 'series'>>(dataset: T): T {
  if (!Array.isArray(dataset?.series)) return dataset
  dataset.series.forEach((series, seriesIndex) => {
    if (!Array.isArray(series?.points)) return
    const where = `series[${seriesIndex}]`
    series.points.forEach((point, index) => checkPoint(point, series, `${where}.points[${index}]`))
    checkInputs(series.cagr_provenance, `${where}.cagr_provenance`)
    checkInputs(series.window_pp_provenance, `${where}.window_pp_provenance`)
  })
  return dataset
}

/** Whether a point's `basis` comparison reads n/m because a later filing reports a different value for one or both of
 *  its periods, not because its values change sign. */
export const basisChanged = (point: Pick<AnalysisPoint, LaterFilingBasis | `${LaterFilingBasis}_first_reported`> | null | undefined, basis: LaterFilingBasis): boolean =>
  point?.[basis] === 'nm' && point[`${basis}_first_reported`] !== undefined

/** The growth as first reported where `basis` changed (a number, "nm", or null where the own reports give none). */
export const growthAsFirstReported = (point: Pick<AnalysisPoint, `${LaterFilingBasis}_first_reported`>, basis: LaterFilingBasis): GrowthValue | null =>
  point[`${basis}_first_reported`] ?? null
