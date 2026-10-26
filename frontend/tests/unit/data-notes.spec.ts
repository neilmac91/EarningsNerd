import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  groupDataNotes, groupQualityNotes, resolveDataNotes, qualityNotesModelFromWire,
  type DataNoteQuality, type DataNotesDataset, type DataNotesPoint, type DataNotesSeries, type DataNotesWire,
} from '@/features/analysis/lib/dataNotes'
import { decodeCitationDataNotes, decodeDataNotes } from '@/features/analysis/lib/dataNotesContract'
import type { FactProvenance } from '@/features/analysis/lib/provenance'

const provenance = (validation: FactProvenance['validation'], reasons: string[] = []): FactProvenance => ({
  version: 1, method: 'reported', validation, reasons, formula: null, inputs: [],
})

interface GoldenCase {
  name: string
  dataset: DataNotesDataset
  expected: DataNotesWire
  citations?: DataNoteQuality[]
  expected_citation_notes?: DataNotesWire
}
const golden: { version: number; cases: GoldenCase[] } = JSON.parse(readFileSync('../backend/tests/fixtures/analysis_data_notes.json', 'utf8'))

describe('server data notes admission', () => {
  it.each(golden.cases)('shares Python memberships, counts, messages and portable identities: $name', (example) => {
    const before = JSON.stringify(example)
    const legacy = groupDataNotes(example.dataset)
    expect({ version: 1, notes: legacy.notes, totals: legacy.totals }).toEqual(example.expected)
    const admitted = decodeDataNotes(example.expected, example.dataset)
    expect(admitted).toEqual(example.expected)
    const report = { ...example.dataset, data_notes: admitted }
    const resolved = resolveDataNotes(report)
    expect(resolved.notes).toBe(admitted.notes)
    expect(resolved.totals).toBe(admitted.totals)
    if (example.citations && example.expected_citation_notes) {
      const combined = groupQualityNotes(example.citations, legacy)
      expect({ version: 1, notes: combined.notes, totals: legacy.totals }).toEqual(example.expected_citation_notes)
      const completion = decodeCitationDataNotes(example.expected_citation_notes, report, example.citations)
      expect(completion).toEqual(example.expected_citation_notes)
      const model = qualityNotesModelFromWire(completion.notes)
      for (const citation of example.citations) expect(model.noteForQuality(citation)).toEqual(combined.noteForQuality(citation))
    }
    expect(JSON.stringify(example)).toBe(before)
  })

  it('retains admitted server copy, letters, ordering and totals across lookups', () => {
    const example = golden.cases[0]
    const wire = structuredClone(example.expected)
    wire.notes.reverse().forEach((note, index) => {
      note.letter = `z${String.fromCharCode(97 + index)}`
      note.id = `analysis-data-note-${note.letter}`
      note.message = `Server explanation ${index}`
    })
    const admitted = decodeDataNotes(wire, example.dataset)
    const model = resolveDataNotes({ ...example.dataset, data_notes: admitted })
    expect(model.notes).toEqual(wire.notes)
    expect(model.totals).toBe(admitted.totals)
    for (const note of admitted.notes) {
      const quality: DataNoteQuality = { value: note.kind === 'unavailable' ? null : 1, provenance: provenance(note.kind === 'review' ? 'needs_review' : 'unavailable', note.reasons) }
      expect(model.noteForQuality(quality)).toBe(note)
    }
  })

  it('uses legacy grouping only when the server field is absent', () => {
    const report = golden.cases[0].dataset
    expect(resolveDataNotes(report).notes).toEqual(groupDataNotes(report).notes)
    for (const data_notes of [undefined, null]) {
      expect(() => resolveDataNotes({ ...report, data_notes } as unknown as DataNotesDataset)).toThrow()
      expect(() => decodeDataNotes(data_notes, report)).toThrow('Invalid analysis data notes')
    }
  })

  it.each([
    ['unsupported version', (wire: DataNotesWire) => { Object.assign(wire, { version: 3 }) }],
    ['fractional total', (wire: DataNotesWire) => { wire.totals.total = 1.5 }],
    ['unsafe total', (wire: DataNotesWire) => { wire.totals.total = Number.MAX_SAFE_INTEGER + 1 }],
    ['duplicate note', (wire: DataNotesWire) => { wire.notes.push(structuredClone(wire.notes[0])) }],
    ['incorrect key', (wire: DataNotesWire) => { wire.notes[0].key = 'review' }],
    ['incorrect id', (wire: DataNotesWire) => { wire.notes[0].id = 'analysis-data-note-z' }],
    ['invalid letter', (wire: DataNotesWire) => { wire.notes[0].letter = 'A'; wire.notes[0].id = 'analysis-data-note-A' }],
    ['missing message', (wire: DataNotesWire) => { wire.notes[0].message = '' }],
    ['incorrect basis count', (wire: DataNotesWire) => { wire.notes[0].counts.qoq++ }],
  ])('rejects %s instead of silently regrouping it', (_name, mutate) => {
    const example = golden.cases[0]
    const wire = structuredClone(example.expected)
    mutate(wire)
    expect(() => decodeDataNotes(wire, example.dataset)).toThrow('Invalid analysis data notes')
  })

  it('decodes a version 2 envelope as version 1: the shape is the same, and version 1 still decodes', () => {
    const example = golden.cases.find((entry) => entry.citations && entry.expected_citation_notes)!
    for (const version of [1, 2] as const) {
      const wire = { ...structuredClone(example.expected), version }
      expect(decodeDataNotes(wire, example.dataset)).toEqual(wire)
      const report = { ...example.dataset, data_notes: wire }
      const citationWire = { ...structuredClone(example.expected_citation_notes!), version }
      expect(decodeCitationDataNotes(citationWire, report, example.citations!)).toEqual(citationWire)
    }
  })

  it('rejects internally balanced totals that falsely promote a review value to passed', () => {
    const example = golden.cases[0]
    const wire = structuredClone(example.expected)
    wire.totals.reviewValues--
    wire.totals.passed++
    expect(wire.totals.reviewValues + wire.totals.passed + wire.totals.unknown + wire.totals.unavailable).toBe(wire.totals.total)
    expect(() => decodeDataNotes(wire, example.dataset)).toThrow('disagrees with dataset quality')
  })

  it.each(['omitted', 'duplicate', 'misassigned', 'wrong label', 'extra passed value'] as const)('rejects %s value membership', (mutation) => {
    const original = dataset([series('cash', [point('2024Q1', { provenance: review('unit_mismatch') }), point('2024Q2', { provenance: review('source_conflict') })]), series('passed', [point('2024Q1'), point('2024Q2')])])
    const grouped = groupDataNotes(original)
    const wire: DataNotesWire = { version: 1, notes: grouped.notes, totals: grouped.totals }
    const ref = wire.notes[0].values[0]
    if (mutation === 'omitted') wire.notes[0].values = []
    if (mutation === 'duplicate') wire.notes[0].values.push({ ...ref })
    if (mutation === 'misassigned') wire.notes[1].values.push(wire.notes[0].values.pop()!)
    if (mutation === 'wrong label') ref.label = 'Other metric'
    if (mutation === 'extra passed value') wire.notes[0].values.push({ concept: 'passed', label: 'passed', period: '2024Q1' })
    expect(() => decodeDataNotes(wire, original)).toThrow('Invalid analysis data notes')
  })

  it('rejects an omitted comparison even when the remaining basis count and total agree', () => {
    const example = golden.cases.find((entry) => entry.name === 'annual_windows_and_comparison_only_issues')!
    const wire = structuredClone(example.expected)
    const note = wire.notes.find((entry) => entry.comparisons.length)!
    const removed = note.comparisons.pop()!
    note.counts[removed.basis]--
    if (note.kind === 'review') wire.totals.reviewComparisons--
    expect(() => decodeDataNotes(wire, example.dataset)).toThrow('dataset concerns are missing')
  })

  it.each(['duplicate', 'misassigned', 'wrong basis'] as const)('rejects %s comparison membership', (mutation) => {
    const original = dataset([series('cash', [point('2024Q1'), point('2024Q2', {
      qoq: 0, qoq_provenance: review('unit_mismatch'), yoy: 'nm', yoy_provenance: review('source_conflict'),
    })])])
    const grouped = groupDataNotes(original)
    const wire: DataNotesWire = { version: 1, notes: grouped.notes, totals: grouped.totals }
    const first = wire.notes[0]
    if (mutation === 'duplicate') { first.comparisons.push({ ...first.comparisons[0] }); first.counts.qoq++ }
    if (mutation === 'misassigned') { wire.notes[1].comparisons.push(first.comparisons.pop()!); first.counts.qoq--; wire.notes[1].counts.qoq++ }
    if (mutation === 'wrong basis') { first.comparisons[0].basis = 'cagr'; first.counts.qoq--; first.counts.cagr++ }
    expect(() => decodeDataNotes(wire, original)).toThrow('Invalid analysis data notes')
  })

  it.each(['period', 'concept', 'point'] as const)('rejects ambiguous duplicate dataset %s identities at ingress', (field) => {
    const example = golden.cases[0]
    const original = structuredClone(example.dataset)
    if (field === 'period') original.periods = [...original.periods, original.periods[0]]
    if (field === 'concept') original.series = [...original.series, original.series[0]]
    if (field === 'point') original.series[0].points = [...original.series[0].points, original.series[0].points[0]]
    expect(() => decodeDataNotes(example.expected, original)).toThrow('contains duplicates')
  })

  it('retains citation concerns even when the matching report value explicitly passed', () => {
    const original = dataset([series('revenue', [point('2024Q1'), point('2024Q2')])])
    const base = groupDataNotes(original)
    const citation = { provenance: review('source_conflict') }
    const supplemental = groupQualityNotes([citation], base)
    const wire: DataNotesWire = { version: 1, notes: supplemental.notes, totals: base.totals }
    const admitted = decodeCitationDataNotes(wire, original, [citation])
    expect(admitted.notes[0]).toMatchObject({ kind: 'review', values: [], comparisons: [] })
    expect(admitted.totals).toMatchObject({ passed: 2, reviewValues: 0, reviewComparisons: 0 })
    expect(() => decodeCitationDataNotes({ ...wire, notes: [] }, original, [citation])).toThrow('citation concerns are missing')
  })

  it('preserves sparse supplemental letters after the report but rejects an earlier unused letter', () => {
    const original = dataset([series('cash', [point('2024Q1', { provenance: review('unit_mismatch') }), point('2024Q2')])])
    const grouped = groupDataNotes(original)
    grouped.notes[0].letter = 'z'
    grouped.notes[0].id = 'analysis-data-note-z'
    const report = { ...original, data_notes: decodeDataNotes({ version: 1, notes: grouped.notes, totals: grouped.totals }, original) }
    const citation = { provenance: review('source_conflict') }
    const combined = groupQualityNotes([citation], resolveDataNotes(report))
    const wire: DataNotesWire = { version: 1, notes: combined.notes, totals: grouped.totals }
    wire.notes[1] = { ...wire.notes[1], letter: 'az', id: 'analysis-data-note-az', message: 'Server citation explanation.' }
    expect(decodeCitationDataNotes(wire, report, [citation]).notes[1]).toEqual(wire.notes[1])
    wire.notes[1].letter = 'y'
    wire.notes[1].id = 'analysis-data-note-y'
    expect(() => decodeCitationDataNotes(wire, report, [citation])).toThrow('supplement letters must follow')
  })

  it.each(['prefix', 'totals', 'omitted', 'extra', 'reference', 'earlier letter'] as const)('rejects a citation envelope with %s changes', (mutation) => {
    const example = golden.cases.find((entry) => entry.name === 'all_known_reason_messages_and_supplements_after_z')!
    const wire = structuredClone(example.expected_citation_notes!)
    const original = { ...example.dataset, data_notes: decodeDataNotes(example.expected, example.dataset) }
    const firstSupplement = wire.notes[example.expected.notes.length]
    if (mutation === 'prefix') wire.notes[0].message = 'Changed report explanation'
    if (mutation === 'totals') wire.totals.passed++
    if (mutation === 'omitted') wire.notes.pop()
    if (mutation === 'extra') firstSupplement.key = '["review",["invented"]]'
    if (mutation === 'reference') firstSupplement.values.push({ concept: 'unlisted', label: 'Unlisted', period: 'FY2024' })
    if (mutation === 'earlier letter') { firstSupplement.letter = 'a'; firstSupplement.id = 'analysis-data-note-a' }
    expect(() => decodeCitationDataNotes(wire, original, example.citations!)).toThrow('Invalid analysis data notes')
  })
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
