import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { noteMarksFigure, RECORD_ONLY_REASONS, type DataNotesWire } from '@/features/analysis/lib/dataNotes'

/**
 * Rule-12 gate for the quiet notation (D-061; DESIGN.md, the Calculation Provenance Rule): a figure carries a mark only
 * where its note questions the number, a review note with a reason other than the record-only legacy_calculation.
 * Unknown and unavailable notes never mark. Every note stays in the evidence dialog and the data notes; the rule
 * applies where marks render, never to the notes model.
 *
 * 1. The helper. Each case of the shared notes fixture names the letters that mark (`marked_letters`, over the citation
 *    notes where a case has them); noteMarksFigure must pick exactly those. The backend asserts that one case covers
 *    every known reason (test_analysis_data_notes.py), so a new reason has to be classified here to pass.
 */

interface GoldenCase {
  name: string
  expected: DataNotesWire
  expected_citation_notes?: DataNotesWire
  marked_letters: string[]
}
const golden: { cases: GoldenCase[] } = JSON.parse(readFileSync('../backend/tests/fixtures/analysis_data_notes.json', 'utf8'))
const notesOf = (example: GoldenCase) => (example.expected_citation_notes ?? example.expected).notes
const allNotes = golden.cases.flatMap(notesOf)

describe('which data notes mark their figure (D-061)', () => {
  it.each(golden.cases)('marks exactly the shared fixture\'s marked_letters: $name', (example) => {
    expect(Array.isArray(example.marked_letters), 'every case names its marked letters').toBe(true)
    expect(notesOf(example).filter(noteMarksFigure).map((note) => note.letter)).toEqual(example.marked_letters)
  })

  it('is tested on every kind of note the rule tells apart', () => {
    const recordOnly = (reasons: string[]) => reasons.length > 0 && reasons.every((reason) => RECORD_ONLY_REASONS.has(reason))
    // A review note about the record alone stays unmarked; a review note that mixes it with a questioning reason marks.
    expect(allNotes.some((note) => note.kind === 'review' && recordOnly(note.reasons) && !noteMarksFigure(note)), 'an unmarked record-only review note').toBe(true)
    expect(allNotes.some((note) => note.kind === 'review' && note.reasons.some((reason) => RECORD_ONLY_REASONS.has(reason)) && !recordOnly(note.reasons) && noteMarksFigure(note)), 'a marked mixed note').toBe(true)
    expect(allNotes.some((note) => note.kind === 'unknown' && !noteMarksFigure(note)), 'an unmarked unknown note').toBe(true)
    expect(allNotes.some((note) => note.kind === 'unavailable' && !noteMarksFigure(note)), 'an unmarked unavailable note').toBe(true)
  })
})
