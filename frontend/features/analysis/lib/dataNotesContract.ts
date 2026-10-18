import {
  dataNoteIssue, dataNoteKey, resolveDataNotes,
  type DataNote, type DataNoteBasis, type DataNoteKind, type DataNoteQuality,
  type DataNotesDataset, type DataNotesTotals, type DataNotesWire,
} from '@/features/analysis/lib/dataNotes'

const bases: readonly DataNoteBasis[] = ['qoq', 'yoy', 'cagr', 'window_pp']
const totalFields = ['reviewValues', 'reviewComparisons', 'unavailable', 'passed', 'unknown', 'calculated', 'total'] as const

/** The decoder's own rejection of a payload. A caller catches this class alone: a plain TypeError from
 * inside the decoder (a read on undefined, a call on a non-function) is a defect and propagates. */
export class DataNotesRejection extends TypeError {
  constructor(detail: string) {
    super(`Invalid analysis data notes: ${detail}`)
    this.name = 'DataNotesRejection'
  }
}

function invalid(detail: string): never {
  throw new DataNotesRejection(detail)
}

function record(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(`${field} must be an object`)
  return value as Record<string, unknown>
}

function string(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.length) invalid(`${field} must be a nonempty string`)
  return value
}

function array(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value)) invalid(`${field} must be an array`)
  return value
}

function count(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) invalid(`${field} must be a nonnegative safe integer`)
  return value
}

function unique(values: readonly string[], field: string) {
  if (new Set(values).size !== values.length) invalid(`${field} contains duplicates`)
}

function valueIdentity(value: { concept: string; period: string }): string {
  return JSON.stringify([value.concept, value.period])
}

function comparisonIdentity(value: { concept: string; period: string; basis: DataNoteBasis }): string {
  return JSON.stringify([value.concept, value.period, value.basis])
}

/** Shape-only admission is also used for the separately bound narrative envelope. */
export function decodeDataNoteList(value: unknown): DataNote[] {
  const notes = array(value, 'notes').map((entry, index): DataNote => {
    const raw = record(entry, `notes[${index}]`)
    if (raw.kind !== 'review' && raw.kind !== 'unknown' && raw.kind !== 'unavailable') invalid('unsupported note kind')
    const kind: DataNoteKind = raw.kind
    const reasons = array(raw.reasons, 'reasons').map((reason) => string(reason, 'reason'))
    if (!reasons.length || JSON.stringify(reasons) !== JSON.stringify([...new Set(reasons)].sort())) invalid('reasons must be a nonempty canonical set')
    const key = string(raw.key, 'key')
    if (key !== dataNoteKey(kind, reasons)) invalid('key does not match its quality identity')
    const letter = string(raw.letter, 'letter')
    if (!/^[a-z]+$/.test(letter)) invalid('letter must use lowercase base-26 letters')
    const id = string(raw.id, 'id')
    if (id !== `analysis-data-note-${letter}`) invalid('id does not match its letter')
    const values = array(raw.values, 'values').map((entry) => {
      const ref = record(entry, 'value reference')
      return { concept: string(ref.concept, 'concept'), label: string(ref.label, 'label'), period: string(ref.period, 'period') }
    })
    const comparisons = array(raw.comparisons, 'comparisons').map((entry) => {
      const ref = record(entry, 'comparison reference')
      if (!bases.includes(ref.basis as DataNoteBasis)) invalid('unsupported comparison basis')
      return { concept: string(ref.concept, 'concept'), label: string(ref.label, 'label'), period: string(ref.period, 'period'), basis: ref.basis as DataNoteBasis }
    })
    const rawCounts = record(raw.counts, 'counts')
    const counts = Object.fromEntries(bases.map((basis) => [basis, count(rawCounts[basis], `counts.${basis}`)])) as DataNote['counts']
    for (const basis of bases) {
      if (counts[basis] !== comparisons.filter((ref) => ref.basis === basis).length) invalid(`counts.${basis} disagrees with its references`)
    }
    return { key, id, letter, kind, reasons, message: string(raw.message, 'message'), values, comparisons, counts }
  })
  for (const field of ['key', 'id', 'letter'] as const) unique(notes.map((note) => note[field]), field)
  unique(notes.flatMap((note) => note.values.map(valueIdentity)), 'value references')
  unique(notes.flatMap((note) => note.comparisons.map(comparisonIdentity)), 'comparison references')
  return notes
}

function decodeEnvelope(value: unknown): DataNotesWire {
  const raw = record(value, 'data_notes')
  if (raw.version !== 1) invalid('unsupported version')
  const totals = record(raw.totals, 'totals')
  return {
    version: 1, notes: decodeDataNoteList(raw.notes),
    totals: Object.fromEntries(totalFields.map((field) => [field, count(totals[field], `totals.${field}`)])) as unknown as DataNotesTotals,
  }
}

function checkedIssue(quality: DataNoteQuality) {
  if (quality.provenance != null) {
    const provenance = record(quality.provenance, 'source provenance')
    if (provenance.reasons != null) array(provenance.reasons, 'source reasons').forEach((reason) => string(reason, 'source reason'))
  }
  return dataNoteIssue(quality)
}

type ExpectedRef = { key: string; label: string }

/** Check quality membership, not financial arithmetic. Server copy, order and letters survive admission. */
export function decodeDataNotes(value: unknown, dataset: DataNotesDataset): DataNotesWire {
  const wire = decodeEnvelope(value)
  const expectedValues = new Map<string, ExpectedRef>()
  const expectedComparisons = new Map<string, ExpectedRef>()
  const expectedKeys = new Set<string>()
  const totals: DataNotesTotals = { reviewValues: 0, reviewComparisons: 0, unavailable: 0, passed: 0, unknown: 0, calculated: 0, total: 0 }
  if (dataset.mode !== 'quarterly' && dataset.mode !== 'annual') invalid('unsupported dataset mode')
  const periods = dataset.periods.map((period) => string(period.key, 'dataset period'))
  unique(periods, 'dataset periods')
  unique(dataset.series.map((series) => string(series.concept, 'dataset concept')), 'dataset concepts')

  function comparison(concept: string, label: string, period: string, basis: DataNoteBasis, quality: DataNoteQuality) {
    if (quality.value == null) return
    if (quality.value !== 'nm' && (typeof quality.value !== 'number' || !Number.isFinite(quality.value))) invalid('comparison value must be finite or nm')
    const issue = checkedIssue(quality)
    if (!issue) return
    expectedComparisons.set(comparisonIdentity({ concept, period, basis }), { key: issue.key, label })
    expectedKeys.add(issue.key)
    if (issue.kind === 'review') totals.reviewComparisons++
  }

  for (const series of dataset.series) {
    const label = string(series.label, 'dataset label')
    unique(series.points.map((point) => string(point.period, 'point period')), 'point periods')
    const points = new Map(series.points.map((point) => [point.period, point]))
    for (const period of periods) {
      const point = points.get(period) ?? { period, value: null }
      if (point.value !== null && (typeof point.value !== 'number' || !Number.isFinite(point.value))) invalid('point value must be finite or null')
      const issue = checkedIssue(point)
      totals.total++
      if (point.value === null) totals.unavailable++
      else {
        if (issue?.kind === 'review') totals.reviewValues++
        else if (issue?.kind === 'unknown') totals.unknown++
        else totals.passed++
        if (point.provenance ? point.provenance.method === 'calculated' : point.derived) totals.calculated++
      }
      if (issue) {
        expectedValues.set(valueIdentity({ concept: series.concept, period }), { key: issue.key, label })
        expectedKeys.add(issue.key)
      }
      for (const basis of dataset.mode === 'quarterly' ? ['qoq', 'yoy'] as const : ['yoy'] as const) {
        comparison(series.concept, label, period, basis, { value: point[basis], provenance: point[`${basis}_provenance`], reconciled: point[`${basis}_reconciled`] })
      }
    }
    if (dataset.mode === 'annual') {
      for (const basis of ['cagr', 'window_pp'] as const) {
        const period = string((basis === 'cagr' ? series.cagr_window : series.window_pp_range) ?? dataset.period_key, 'window period')
        comparison(series.concept, label, period, basis, { value: series[basis], provenance: series[`${basis}_provenance`], reconciled: series[`${basis}_reconciled`] })
      }
    }
  }

  for (const note of wire.notes) {
    if (!expectedKeys.delete(note.key)) invalid('note has no matching dataset concern')
    for (const ref of note.values) {
      const identity = valueIdentity(ref)
      const expected = expectedValues.get(identity)
      if (!expected || expected.key !== note.key || expected.label !== ref.label) invalid('value reference does not match dataset quality')
      expectedValues.delete(identity)
    }
    for (const ref of note.comparisons) {
      const identity = comparisonIdentity(ref)
      const expected = expectedComparisons.get(identity)
      if (!expected || expected.key !== note.key || expected.label !== ref.label) invalid('comparison reference does not match dataset quality')
      expectedComparisons.delete(identity)
    }
  }
  if (expectedValues.size || expectedComparisons.size || expectedKeys.size) invalid('dataset concerns are missing')
  for (const field of totalFields) if (wire.totals[field] !== totals[field]) invalid(`totals.${field} disagrees with dataset quality`)
  return wire
}

function noteIdentity(note: DataNote): string {
  return JSON.stringify([
    note.key, note.id, note.letter, note.kind, note.reasons, note.message,
    note.values.map((ref) => [ref.concept, ref.label, ref.period]),
    note.comparisons.map((ref) => [ref.concept, ref.label, ref.period, ref.basis]),
    bases.map((basis) => note.counts[basis]),
  ])
}

function laterLetter(letter: string, previous: string): boolean {
  return letter.length > previous.length || (letter.length === previous.length && letter > previous)
}

/** A completion can append citation concerns, but cannot relabel or rewrite its report. */
export function decodeCitationDataNotes(value: unknown, dataset: DataNotesDataset, citations: readonly DataNoteQuality[]): DataNotesWire {
  const wire = decodeEnvelope(value)
  const report = resolveDataNotes(dataset)
  if (wire.notes.length < report.notes.length || report.notes.some((note, index) => noteIdentity(note) !== noteIdentity(wire.notes[index]))) invalid('citation notes changed the report prefix')
  for (const field of totalFields) if (wire.totals[field] !== report.totals[field]) invalid('citation notes changed report totals')

  const reportKeys = new Set(report.notes.map((note) => note.key))
  let lastLetter = report.notes.reduce((last, note) => laterLetter(note.letter, last) ? note.letter : last, '')
  const supplementalKeys = new Set<string>()
  for (const citation of citations) {
    const issue = checkedIssue(citation)
    if (issue && !reportKeys.has(issue.key)) supplementalKeys.add(issue.key)
  }
  for (const note of wire.notes.slice(report.notes.length)) {
    if (!laterLetter(note.letter, lastLetter)) invalid('supplement letters must follow the report and earlier supplements')
    lastLetter = note.letter
    if (!supplementalKeys.delete(note.key)) invalid('supplement has no matching citation concern')
    if (note.values.length || note.comparisons.length) invalid('citation supplement must not add report references')
  }
  if (supplementalKeys.size) invalid('citation concerns are missing')
  return wire
}
