import type { AnalysisDataset, AnalysisSeries, GrowthValue } from '@/features/analysis/api/analysis-api'
import { REASON_SUMMARIES, reasonText, SUMMARY_FALLBACK, type FactProvenance } from '@/features/analysis/lib/provenance'

export type DataNoteKind = 'review' | 'unknown' | 'unavailable'
export type DataNoteBasis = 'qoq' | 'yoy' | 'cagr' | 'window_pp'
type PointBasis = Extract<DataNoteBasis, 'qoq' | 'yoy'>
type NoteProvenance = Pick<FactProvenance, 'method' | 'validation' | 'reasons'>

/** Only quality fields are consumed; source inputs remain owned by the original payload. */
export interface DataNoteQuality {
  value?: number | 'nm' | null
  reconciled?: boolean | null
  provenance?: NoteProvenance | null
}

export interface DataNotesPoint extends DataNoteQuality {
  period: string
  value: number | null
  derived?: boolean
  qoq?: GrowthValue | null
  yoy?: GrowthValue | null
  qoq_reconciled?: boolean | null
  yoy_reconciled?: boolean | null
  qoq_provenance?: NoteProvenance | null
  yoy_provenance?: NoteProvenance | null
}

export interface DataNotesSeries extends Pick<AnalysisSeries, 'concept' | 'label' | 'percent' | 'cagr' | 'cagr_window' | 'window_pp' | 'window_pp_range' | 'cagr_reconciled' | 'window_pp_reconciled'> {
  cagr_provenance?: NoteProvenance | null
  window_pp_provenance?: NoteProvenance | null
  points: readonly DataNotesPoint[]
}

export interface DataNotesDataset extends Pick<AnalysisDataset, 'mode' | 'period_key'> {
  periods: readonly { key: string }[]
  series: readonly DataNotesSeries[]
  data_notes?: DataNotesWire
}

export interface DataNoteValueRef {
  concept: string
  label: string
  period: string
}

export interface DataNoteComparisonRef extends DataNoteValueRef {
  basis: DataNoteBasis
}

export interface DataNote {
  key: string
  id: string
  letter: string
  kind: DataNoteKind
  reasons: string[]
  message: string
  values: DataNoteValueRef[]
  comparisons: DataNoteComparisonRef[]
  counts: Record<DataNoteBasis, number>
}

/** Reasons that describe a figure's record, not its value (D-061). The list is closed: any other reason marks, so a new
 *  reason shows until someone classifies it here. The backend's data_notes.RECORD_ONLY_REASONS holds the same list:
 *  the shared notes fixture's record_only_reasons pins both, and its marked_letters the rule. */
export const RECORD_ONLY_REASONS: ReadonlySet<string> = new Set(['legacy_calculation'])

/** Whether a note puts a mark beside its figure: a review note with at least one reason that questions the number.
 *  Unknown and unavailable notes never mark (a gap shows its dash; a missing record makes no claim either way). Every
 *  note still appears in the evidence dialog and the data notes, and note kinds, reasons, letters and totals are
 *  untouched: the rule applies where a mark renders, never to the notes model. */
export function noteMarksFigure(note: Pick<DataNote, 'kind' | 'reasons'> | null | undefined): boolean {
  return note?.kind === 'review'
    && (note.reasons.length === 0 || note.reasons.some((reason) => !RECORD_ONLY_REASONS.has(reason)))
}

/** A marked note's words in the fine print: each questioning reason's clause (REASON_SUMMARIES, or SUMMARY_FALLBACK),
 *  once, in reason order, joined by "; ". The backend's data_notes.note_summary writes the same, for the exports (WP3). */
export function noteSummary(reasons: readonly string[]): string {
  const clauses = reasons.filter((reason) => !RECORD_ONLY_REASONS.has(reason))
    .map((reason) => Object.hasOwn(REASON_SUMMARIES, reason) ? REASON_SUMMARIES[reason] : SUMMARY_FALLBACK)
  return [...new Set(clauses.length ? clauses : [SUMMARY_FALLBACK])].join('; ')
}

/** The note when it marks its figure, else null: the form DataNoteMark and the chart lookups take. */
export function markedNote<T extends Pick<DataNote, 'kind' | 'reasons'>>(note: T | null | undefined): T | null {
  return note && noteMarksFigure(note) ? note : null
}

export interface DataNotesTotals {
  reviewValues: number
  reviewComparisons: number
  unavailable: number
  passed: number
  unknown: number
  calculated: number
  /** All metric-period slots: passed + reviewValues + unknown + unavailable. */
  total: number
}

/** Versioned server metadata, admitted once at the API boundary. Version 2 has the same shape as 1: only the reasons'
 *  words and the letter order (marked notes first) differ, and the local grouper writes 2. A saved version 1 envelope
 *  (the landing sample, a tab opened before the server moved) still decodes with its stored words and letters. */
export interface DataNotesWire {
  version: 1 | 2
  notes: DataNote[]
  totals: DataNotesTotals
}

export interface QualityNotesModel {
  notes: DataNote[]
  noteForQuality(value: DataNoteQuality): DataNote | null
}

export interface DataNotesModel extends QualityNotesModel {
  totals: DataNotesTotals
  noteFor(point: DataNoteQuality): DataNote | null
  noteForComparison(point: DataNotesPoint, basis: PointBasis): DataNote | null
  noteForWindow(series: DataNotesSeries): DataNote | null
}

type Issue = Pick<DataNote, 'key' | 'kind' | 'reasons'>

/** Compact ASCII JSON and UTF-16 reason ordering are shared with the Python producer. */
export function dataNoteKey(kind: DataNoteKind, reasons: readonly string[]): string {
  return JSON.stringify([kind, [...new Set(reasons)].sort()]).replace(/[\u007f-\uffff]/g,
    (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`)
}

/** Quality identity only: this never infers validation from calculation or citation status. */
export function dataNoteIssue(value: DataNoteQuality): Issue | null {
  const validation = value.provenance?.validation
  const kind: DataNoteKind | null = value.value === null ? 'unavailable'
    : (value.provenance ? validation === 'needs_review' : value.reconciled === false) ? 'review'
      : validation === 'passed' ? null : 'unknown'
  if (!kind) return null
  const supplied = value.provenance?.reasons ?? []
  const fallback = kind === 'unavailable' ? 'not_in_dataset'
    : kind === 'unknown' ? 'legacy_unknown' : 'source_check_needed'
  const reasons = [...new Set(supplied.length ? supplied : [fallback])].sort()
  return { kind, reasons, key: dataNoteKey(kind, reasons) }
}

function letterFor(index: number): string {
  let letter = ''
  for (let value = index + 1; value > 0; value = Math.floor((value - 1) / 26)) {
    letter = String.fromCharCode(97 + (value - 1) % 26) + letter
  }
  return letter
}

function createGroups() {
  const groups = new Map<string, DataNote>()
  function add(value: DataNoteQuality): DataNote | null {
    const issue = dataNoteIssue(value)
    if (!issue) return null
    let note = groups.get(issue.key)
    if (!note) {
      note = {
        ...issue, id: '', letter: '', message: issue.reasons.map(reasonText).join(' '),
        values: [], comparisons: [], counts: { qoq: 0, yoy: 0, cagr: 0, window_pp: 0 },
      }
      groups.set(issue.key, note)
    }
    return note
  }
  function finish(): QualityNotesModel {
    // Marked notes take the first letters, so a page's first visible letter is "a"; then review, unknown and
    // unavailable notes. The sort is stable, so report order holds within each.
    const order: Record<DataNoteKind, number> = { review: 0, unknown: 1, unavailable: 2 }
    const notes = [...groups.values()].sort((a, b) =>
      Number(!noteMarksFigure(a)) - Number(!noteMarksFigure(b)) || order[a.kind] - order[b.kind])
    notes.forEach((note, index) => {
      note.letter = letterFor(index)
      note.id = `analysis-data-note-${note.letter}`
    })
    return {
      notes,
      noteForQuality(value) {
        const issue = dataNoteIssue(value)
        return issue ? groups.get(issue.key) ?? null : null
      },
    }
  }
  return { add, finish }
}

/** Citation-only concerns supplement the report without relabelling it or changing its totals. */
export function groupQualityNotes(values: readonly DataNoteQuality[], existing?: QualityNotesModel): QualityNotesModel {
  const groups = createGroups()
  values.forEach((value) => groups.add(value))
  const supplemental = groups.finish()
  if (!existing) return supplemental

  const notes = [...existing.notes]
  const byKey = new Map(notes.map((note) => [note.key, note]))
  // Continue after the final report letter, including multi-letter or filtered note lists.
  let nextIndex = notes.reduce((last, note) => Math.max(last,
    [...note.letter].reduce((value, char) => value * 26 + char.charCodeAt(0) - 96, 0)), 0)
  for (const note of supplemental.notes) {
    if (byKey.has(note.key)) continue
    const letter = letterFor(nextIndex++)
    const added = { ...note, letter, id: `analysis-data-note-${letter}` }
    notes.push(added)
    byKey.set(added.key, added)
  }
  return {
    notes,
    noteForQuality(value) {
      const issue = dataNoteIssue(value)
      return issue ? byKey.get(issue.key) ?? null : null
    },
  }
}

function pointComparison(point: DataNotesPoint, basis: PointBasis): DataNoteQuality {
  return { value: point[basis], provenance: point[`${basis}_provenance`], reconciled: point[`${basis}_reconciled`] }
}

function windowComparison(series: DataNotesSeries, basis: 'cagr' | 'window_pp'): DataNoteQuality {
  return { value: series[basis], provenance: series[`${basis}_provenance`], reconciled: series[`${basis}_reconciled`] }
}

/** Consumers retain the server's copy, ordering and letters without regrouping admitted notes. */
export function qualityNotesModelFromWire(notes: DataNote[]): QualityNotesModel {
  const byKey = new Map(notes.map((note) => [note.key, note]))
  return {
    notes,
    noteForQuality(value) {
      const issue = dataNoteIssue(value)
      return issue ? byKey.get(issue.key) ?? null : null
    },
  }
}

export function dataNotesModelFromWire(wire: DataNotesWire, mode: DataNotesDataset['mode']): DataNotesModel {
  const model = qualityNotesModelFromWire(wire.notes)
  return {
    ...model, totals: wire.totals, noteFor: model.noteForQuality,
    noteForComparison(point, basis) {
      if (point[basis] == null || (basis === 'qoq' && mode !== 'quarterly')) return null
      return model.noteForQuality(pointComparison(point, basis))
    },
    noteForWindow(series) {
      const basis = series.percent ? 'window_pp' : 'cagr'
      if (mode !== 'annual' || series[basis] == null) return null
      return model.noteForQuality(windowComparison(series, basis))
    },
  }
}

/** Absence is the sole legacy path; present metadata must already have passed the decoder. */
export function resolveDataNotes(dataset: DataNotesDataset): DataNotesModel {
  return Object.hasOwn(dataset, 'data_notes')
    ? dataNotesModelFromWire(dataset.data_notes!, dataset.mode)
    : groupDataNotes(dataset)
}

/** Group concerns once per full report, independently of any presentation. */
export function groupDataNotes(dataset: DataNotesDataset): DataNotesModel {
  const groups = createGroups()
  const totals: DataNotesTotals = { reviewValues: 0, reviewComparisons: 0, unavailable: 0, passed: 0, unknown: 0, calculated: 0, total: 0 }
  const valueIds = new Set<string>()
  const comparisonIds = new Set<string>()
  const periods = [...new Set(dataset.periods.map((period) => period.key))]

  // Build value notes first, in report order; comparison-only reasons follow without being lost.
  for (const series of dataset.series) {
    const points = new Map(series.points.map((point) => [point.period, point]))
    for (const period of periods) {
      const identity = JSON.stringify([series.concept, period])
      if (valueIds.has(identity)) continue
      valueIds.add(identity)
      const point = points.get(period) ?? { period, value: null }
      const note = groups.add(point)
      totals.total++
      if (point.value === null) totals.unavailable++
      else {
        if (note?.kind === 'review') totals.reviewValues++
        else if (note?.kind === 'unknown') totals.unknown++
        else totals.passed++
        if (point.provenance ? point.provenance.method === 'calculated' : point.derived) totals.calculated++
      }
      note?.values.push({ concept: series.concept, label: series.label, period })
    }
  }

  function addComparison(series: DataNotesSeries, period: string, basis: DataNoteBasis, quality: DataNoteQuality) {
    if (quality.value == null) return
    const identity = JSON.stringify([series.concept, period, basis])
    if (comparisonIds.has(identity)) return
    comparisonIds.add(identity)
    const note = groups.add(quality)
    if (!note) return
    note.comparisons.push({ concept: series.concept, label: series.label, period, basis })
    note.counts[basis]++
    if (note.kind === 'review') totals.reviewComparisons++
  }

  for (const series of dataset.series) {
    const points = new Map(series.points.map((point) => [point.period, point]))
    for (const period of periods) {
      const point = points.get(period)
      if (!point) continue
      if (dataset.mode === 'quarterly') addComparison(series, period, 'qoq', pointComparison(point, 'qoq'))
      addComparison(series, period, 'yoy', pointComparison(point, 'yoy'))
    }
    if (dataset.mode === 'annual') {
      addComparison(series, series.cagr_window ?? dataset.period_key, 'cagr', windowComparison(series, 'cagr'))
      addComparison(series, series.window_pp_range ?? dataset.period_key, 'window_pp', windowComparison(series, 'window_pp'))
    }
  }

  return dataNotesModelFromWire({ version: 2, notes: groups.finish().notes, totals }, dataset.mode)
}
