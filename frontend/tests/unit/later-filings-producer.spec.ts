/* =============================================================================
   later-filings-producer.spec.ts — the producer's datasets through the page's decoders (MPA WP5a-B)
   -----------------------------------------------------------------------------
   The page's reader (lib/laterFilings.ts) is the later-filing contract. The backend commits the analysis datasets its
   producer (backend/app/services/trend_analysis/first_reports.py) builds from WP5b's REGN sync and three findings on
   it, each over two windows (backend/tests/fixtures/analysis_first_reports_produced.json), and its own test holds the
   file equal to the producer's output (backend/tests/unit/test_first_reports_wire.py, which says how to regenerate
   it). Here every committed dataset must pass the real decoders unchanged, and REGN's later-filing places must be the
   shared fixture's REGN case at its crossing (D3), so a producer change the page would refuse fails here once the file
   is regenerated.
============================================================================= */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { decodeDataNotes } from '@/features/analysis/lib/dataNotesContract'
import { decodeLaterFilings, laterFilingPlaces } from '@/features/analysis/lib/laterFilings'

const PRODUCED: { datasets: Record<string, AnalysisDataset> } = JSON.parse(
  readFileSync('../backend/tests/fixtures/analysis_first_reports_produced.json', 'utf8'),
)
const SHARED: { cases: { name: string; expected: unknown }[] } = JSON.parse(
  readFileSync('../backend/tests/fixtures/analysis_later_filings.json', 'utf8'),
)

describe("the producer's datasets (WP5a-B) and the page's decoders", () => {
  it('pins the four shapes over both windows', () => {
    expect(Object.keys(PRODUCED.datasets)).toEqual(
      ['regn', 'a-sign-flip', 'a-scale-factor', 'an-inputs-finding'].flatMap((shape) => [`${shape} FY2017..FY2021`, `${shape} FY2018..FY2021`]),
    )
  })

  for (const [name, dataset] of Object.entries(PRODUCED.datasets)) {
    it(`admits ${name} unchanged, its later-filing evidence and its data notes`, () => {
      const sent = structuredClone(dataset)
      expect(decodeLaterFilings(sent)).toEqual(dataset)
      expect(() => decodeDataNotes(sent.data_notes, sent)).not.toThrow()
    })
  }

  it("gives REGN's dataset the shared fixture's values and its crossing's comparisons (D3)", () => {
    // D3 (the founder's, 2026-11-01): growth reads n/m where it crosses a change of basis, so the producer reads REGN's
    // revenue and net margin n/m on FY2018 alone; the shared case, planted under the rule before D3's census, also
    // plants FY2019 and FY2020, a run and a leading edge that now keep their growth.
    const regn = SHARED.cases.find((entry) => entry.name === 'regn_own_reports_beside_later_comparatives')!
    const planted = regn.expected as { values: unknown[]; comparisons: { period: string }[] }
    expect(laterFilingPlaces(PRODUCED.datasets['regn FY2017..FY2021'])).toEqual({
      values: planted.values,
      comparisons: planted.comparisons.filter((place) => place.period === 'FY2018'),
    })
  })
})
