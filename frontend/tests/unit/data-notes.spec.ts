import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  groupDataNotes, groupQualityNotes,
  type DataNoteQuality, type DataNotesDataset, type DataNotesPoint, type DataNotesSeries,
} from '@/features/analysis/lib/dataNotes'
import type { FactProvenance } from '@/features/analysis/lib/provenance'

const provenance = (validation: FactProvenance['validation'], reasons: string[] = []): FactProvenance => ({
  version: 1, method: 'reported', validation, reasons, formula: null, inputs: [],
})
const passed = provenance('passed')
const review = (...reasons: string[]) => provenance('needs_review', reasons)
const point = (period: string, fields: Partial<DataNotesPoint> = {}): DataNotesPoint => ({ period, value: 100, provenance: passed, ...fields })
const series = (concept: string, points: DataNotesPoint[], fields: Partial<DataNotesSeries> = {}): DataNotesSeries => ({
  concept, label: concept, percent: false, cagr: null, points, ...fields,
})
const dataset = (seriesList: DataNotesSeries[], mode: DataNotesDataset['mode'] = 'quarterly'): DataNotesDataset => ({
  mode, period_key: mode === 'annual' ? 'FY2023..FY2024' : '2024Q1..2024Q2',
  periods: (mode === 'annual' ? ['FY2023', 'FY2024'] : ['2024Q1', '2024Q2']).map((key) => ({ key })),
  series: seriesList,
})

describe('analysis data notes', () => {
  it('pins the captured production counts without pretending the prototype is production', () => {
    const fixture: { source: { sha256: string }; dataset: DataNotesDataset } = JSON.parse(readFileSync('tests/unit/fixtures/meta-data-notes.json', 'utf8'))
    const before = JSON.stringify(fixture.dataset)
    const notes = groupDataNotes(fixture.dataset)
    expect(fixture.source.sha256).toBe('adb4ae8b7d393dc262b995fbe5709d1590b58dc5d7ca54d831a05cebf4e43cb1')
    expect(notes.totals).toEqual({ reviewValues: 10, reviewComparisons: 26, unavailable: 4, passed: 226, unknown: 0, calculated: 101, total: 240 })
    expect(notes.notes.map((note) => [note.letter, note.kind, note.reasons, note.values.length])).toEqual([
      ['a', 'review', ['legacy_calculation'], 10],
      ['b', 'unavailable', ['not_in_dataset'], 2],
      ['c', 'unavailable', ['legacy_calculation_not_supported'], 2],
    ])
    expect(notes.notes[0].counts).toEqual({ qoq: 16, yoy: 10, cagr: 0, window_pp: 0 })
    expect(notes.notes[0].values.filter((value) => value.concept === 'current_ratio').map((value) => value.period)).toEqual(['2023Q4', '2024Q4', '2026Q2'])
    expect(JSON.parse(JSON.stringify({ notes: notes.notes, totals: notes.totals }))).toEqual({ notes: notes.notes, totals: notes.totals })
    expect(JSON.stringify(fixture.dataset)).toBe(before)
  })

  it('groups canonical reason sets and uses the same note for copied values and comparisons', () => {
    const first = point('2024Q1', { provenance: review('unit_mismatch', 'source_conflict', 'unit_mismatch') })
    const second = point('2024Q2', { provenance: review('source_conflict', 'unit_mismatch'), qoq: 0, qoq_provenance: review('unit_mismatch', 'source_conflict') })
    const model = groupDataNotes(dataset([series('revenue', [first, second])]))
    expect(model.notes).toHaveLength(1)
    expect(model.notes[0].reasons).toEqual(['source_conflict', 'unit_mismatch'])
    expect(model.notes[0].values).toHaveLength(2)
    expect(model.notes[0].counts.qoq).toBe(1)
    expect(model.noteFor(structuredClone(first))).toBe(model.notes[0])
    expect(model.noteForComparison(structuredClone(second), 'qoq')).toBe(model.notes[0])
    expect(model.noteForQuality({ provenance: review('unit_mismatch', 'source_conflict') })).toBe(model.notes[0])
    expect(model.notes[0].id).toBe('analysis-data-note-a')
  })

  it('retains comparison-only union reasons and unknown codes even when their copy is identical', () => {
    const first = point('2024Q1', { provenance: review('future_a') })
    const second = point('2024Q2', { provenance: review('future_b'), qoq: 'nm', qoq_provenance: review('future_b', 'future_a') })
    const model = groupDataNotes(dataset([series('cash', [first, second])]))
    expect(model.notes.map((note) => note.reasons)).toEqual([['future_a'], ['future_b'], ['future_a', 'future_b']])
    expect(model.notes[0].message).toBe(model.notes[1].message)
    expect(model.notes[0].key).not.toBe(model.notes[1].key)
    expect(model.notes[2].values).toEqual([])
    expect(model.notes[2].comparisons).toEqual([{ concept: 'cash', label: 'cash', period: '2024Q2', basis: 'qoq' }])
    expect(model.noteForComparison(second, 'qoq')).toBe(model.notes[2])
    expect(model.totals.reviewComparisons).toBe(1)
  })

  it('keeps legacy false reviewable and populated unknown validation separate from passed', () => {
    const rows = [
      series('legacy', [point('2024Q1', { provenance: null, reconciled: false, derived: true }), point('2024Q2', { provenance: null, reconciled: true })]),
      series('unknown', [point('2024Q1', { provenance: undefined }), point('2024Q2', { provenance: provenance('unavailable', ['missing_provenance']) })]),
      series('passed', [point('2024Q1', { reconciled: false }), point('2024Q2', { provenance: { ...passed, method: 'calculated' } })]),
    ]
    const model = groupDataNotes(dataset(rows))
    expect(model.totals).toEqual({ reviewValues: 1, reviewComparisons: 0, unavailable: 0, passed: 2, unknown: 3, calculated: 2, total: 6 })
    expect(model.noteFor(rows[0].points[0])?.reasons).toEqual(['source_check_needed'])
    expect(model.noteFor(rows[0].points[1])?.kind).toBe('unknown')
    expect(model.noteFor(rows[1].points[0])?.message).toContain('No verification claim is made')
    expect(model.noteFor(rows[1].points[1])?.kind).toBe('unknown')
    expect(model.noteFor(rows[2].points[0])).toBeNull()
  })

  it('counts absent period slots as unavailable and orders review notes before gaps', () => {
    const reviewed = point('2024Q2', { provenance: review('legacy_calculation') })
    const rows = [series('cash', [reviewed]), series('eps', [point('2024Q1', { value: null, provenance: provenance('unavailable', ['unsupported_eps_calculation']) }), point('2024Q2')])]
    const model = groupDataNotes(dataset(rows))
    expect(model.totals).toMatchObject({ reviewValues: 1, passed: 1, unavailable: 2, total: 4 })
    expect(model.notes.map((note) => [note.letter, note.kind, note.reasons])).toEqual([
      ['a', 'review', ['legacy_calculation']], ['b', 'unavailable', ['not_in_dataset']], ['c', 'unavailable', ['unsupported_eps_calculation']],
    ])
    expect(model.noteFor({ value: null })?.values).toEqual([{ concept: 'cash', label: 'cash', period: '2024Q1' }])
    expect(model.noteFor({ value: null, provenance: provenance('unavailable', ['unsupported_eps_calculation']) })?.letter).toBe('c')
  })

  it('counts only existing comparisons, including zero and nm, and preserves legacy comparison flags', () => {
    const rows = [series('cash', [
      point('2024Q1', { qoq: null, qoq_provenance: review('source_conflict'), yoy_provenance: review('unit_mismatch') }),
      point('2024Q2', { qoq: 'nm', qoq_reconciled: false, yoy: 0, yoy_reconciled: false }),
    ])]
    const model = groupDataNotes(dataset(rows))
    expect(model.totals.reviewValues).toBe(0)
    expect(model.totals.reviewComparisons).toBe(2)
    expect(model.notes).toHaveLength(1)
    expect(model.notes[0].reasons).toEqual(['source_check_needed'])
    expect(model.notes[0].counts).toEqual({ qoq: 1, yoy: 1, cagr: 0, window_pp: 0 })
    expect(model.noteForComparison(rows[0].points[0], 'qoq')).toBeNull()
    expect(model.noteForComparison(rows[0].points[0], 'yoy')).toBeNull()
  })

  it('includes annual CAGR and percentage-point windows with their own actual ranges', () => {
    const income = series('income', [point('FY2023'), point('FY2024', { yoy: 0.2, yoy_provenance: review('legacy_calculation') })], {
      cagr: 0, cagr_window: 'FY2023..FY2024', cagr_reconciled: false,
    })
    const margin = series('margin', [point('FY2023'), point('FY2024')], {
      percent: true, window_pp: -2, window_pp_range: 'FY2023..FY2024', window_pp_provenance: review('source_conflict'),
    })
    const model = groupDataNotes(dataset([income, margin], 'annual'))
    expect(model.totals.reviewValues).toBe(0)
    expect(model.totals.reviewComparisons).toBe(3)
    expect(model.noteForWindow(income)?.comparisons).toEqual([{ concept: 'income', label: 'income', period: 'FY2023..FY2024', basis: 'cagr' }])
    expect(model.noteForWindow(margin)?.counts.window_pp).toBe(1)
    expect(model.noteForWindow({ ...income, cagr: null })).toBeNull()
    expect(groupDataNotes(dataset([income, margin])).noteForWindow(income)).toBeNull()
  })

  it('counts unknown comparison validation honestly without calling it a failed check', () => {
    const p = point('2024Q2', { qoq: 0.1, qoq_reconciled: true })
    const model = groupDataNotes(dataset([series('revenue', [point('2024Q1'), p])]))
    expect(model.totals).toMatchObject({ passed: 2, unknown: 0, reviewComparisons: 0 })
    expect(model.noteForComparison(p, 'qoq')?.kind).toBe('unknown')
    expect(model.notes[0].counts.qoq).toBe(1)
  })

  it('uses full report order and deduplicates metric-period/basis references', () => {
    const p = point('2024Q2', { provenance: review('unit_mismatch'), qoq: 0.1, qoq_provenance: review('unit_mismatch') })
    const s = series('cash', [point('2024Q1'), p])
    const original = dataset([s])
    const duplicated = { ...original, periods: [...original.periods, original.periods[1]], series: [s, structuredClone(s)] }
    const model = groupDataNotes(duplicated)
    expect(model.notes).toEqual(groupDataNotes(original).notes)
    expect(model.totals).toEqual(groupDataNotes(original).totals)
    expect(model.noteFor(structuredClone(p))?.letter).toBe('a')
  })

  it('supports citation-only quality notes without creating values, comparisons or totals', () => {
    const values: DataNoteQuality[] = [
      { reconciled: false }, { provenance: review('source_conflict') }, { reconciled: true },
      { provenance: passed }, { provenance: review('source_conflict') },
    ]
    const model = groupQualityNotes(values)
    expect(model.notes.map((note) => note.kind)).toEqual(['review', 'review', 'unknown'])
    expect(model.notes.every((note) => note.values.length === 0 && note.comparisons.length === 0)).toBe(true)
    expect(model).not.toHaveProperty('totals')
    expect(model.noteForQuality(structuredClone(values[1]))?.letter).toBe('b')
    expect(model.noteForQuality(values[3])).toBeNull()
  })

  it('appends citation-only concerns without changing report letters, counts or citation quality', () => {
    const report = groupDataNotes(dataset([series('revenue', [
      point('2024Q1', { provenance: review('unit_mismatch') }), point('2024Q2'),
    ])]))
    const before = JSON.stringify({ notes: report.notes, totals: report.totals })
    // The dataset's same-period value passed; this citation has only its own legacy false flag.
    const citation = point('2024Q2', { provenance: undefined, reconciled: false })
    const model = groupQualityNotes([citation, { reconciled: true }], report)
    expect(model.notes.map((note) => [note.letter, note.kind, note.reasons])).toEqual([
      ['a', 'review', ['unit_mismatch']], ['b', 'review', ['source_check_needed']], ['c', 'unknown', ['legacy_unknown']],
    ])
    expect(model.notes[0]).toBe(report.notes[0])
    expect(model.noteForQuality(citation)).toBe(model.notes[1])
    expect(model.notes[1].values).toEqual([])
    expect(model.notes[1].comparisons).toEqual([])
    expect(model).not.toHaveProperty('totals')
    expect(JSON.stringify({ notes: report.notes, totals: report.totals })).toBe(before)
    expect(report.noteForQuality(citation)).toBeNull()
    expect(new Set(model.notes.map((note) => note.id)).size).toBe(3)
  })

  it('reuses exact report reason sets and appends after unavailable notes without renumbering', () => {
    const report = groupDataNotes(dataset([series('cash', [
      point('2024Q1', { provenance: review('unit_mismatch', 'source_conflict') }), point('2024Q2', { value: null }),
    ])]))
    const same = { provenance: review('source_conflict', 'unit_mismatch', 'source_conflict') }
    const distinctKind = { provenance: provenance('unavailable', ['source_conflict', 'unit_mismatch']) }
    const model = groupQualityNotes([same, same, distinctKind], report)
    expect(model.notes.map((note) => [note.letter, note.kind])).toEqual([['a', 'review'], ['b', 'unavailable'], ['c', 'unknown']])
    expect(model.noteForQuality(same)).toBe(report.notes[0])
    expect(model.noteForQuality(distinctKind)).toBe(model.notes[2])
    expect(model.notes[1]).toBe(report.notes[1])
  })

  it('continues supplemental letters after z and reuses an already appended concern', () => {
    const existing = groupQualityNotes(Array.from({ length: 27 }, (_, index) => ({ provenance: review(`reason_${index}`) })))
    const extra = { reconciled: false }
    const model = groupQualityNotes([extra], existing)
    expect(model.noteForQuality(extra)?.letter).toBe('ab')
    expect(model.noteForQuality(extra)?.id).toBe('analysis-data-note-ab')
    expect(groupQualityNotes([extra], model).notes).toEqual(model.notes)
    expect(new Set(model.notes.map((note) => note.id)).size).toBe(28)
  })
})
