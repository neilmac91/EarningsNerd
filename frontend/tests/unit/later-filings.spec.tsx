/* =============================================================================
   later-filings.spec.tsx — the page's reader of the later-filing evidence (MPA WP5a-F1)
   -----------------------------------------------------------------------------
   Where a later filing reports a value other than the one a fiscal year's own annual report gave, the producer
   (WP5a-B) will send the own report's value beside the shown one (`first_reported`) and, where a comparison reads n/m
   across the change, the growth as first reported (`{basis}_first_reported`). The page reads them before the producer
   writes them. The shared fixture (backend/tests/fixtures/analysis_later_filings.json) plants that wire shape on
   REGN's own-report values (WP5b) and holds the later-filing places both sides compute; the backend's twin of
   laterFilingPlaces reads the same cases when it lands.
============================================================================= */
import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import api from '@/lib/api/client'
import { getAnalysisDataset, type AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { decodeLaterFilings, LaterFilingsRejection } from '@/features/analysis/lib/laterFilings'

type Ref = { concept: string; label: string; period: string; basis?: string }
interface LaterFilingsCase {
  name: string
  about: string
  dataset: AnalysisDataset
  expected: { values: Ref[]; comparisons: Ref[] }
}
const FIXTURE: { description: string; cases: LaterFilingsCase[] } = JSON.parse(readFileSync('../backend/tests/fixtures/analysis_later_filings.json', 'utf8'))
const CASES = FIXTURE.cases
const planted = (name: string): AnalysisDataset => structuredClone(CASES.find((entry) => entry.name === name)!.dataset)
const REGN = 'regn_own_reports_beside_later_comparatives'
const SIGN_AND_SCALE = 'a_sign_flip_and_a_scale_factor_count_as_figures'
const seriesOf = (dataset: AnalysisDataset, concept: string) => dataset.series.find((series) => series.concept === concept)!
const pointOf = (dataset: AnalysisDataset, concept: string, period: string) => seriesOf(dataset, concept).points.find((point) => point.period === period)!
const range = { mode: 'annual' as const, start_period: 'FY2017', end_period: 'FY2021' }

afterEach(() => { vi.restoreAllMocks() })

describe('the later-filing evidence, decoded where the dataset enters', () => {
  it.each(CASES.map((entry) => [entry.name]))('admits the planted case %s as sent', async (name) => {
    const dataset = planted(name)
    const sent = structuredClone(dataset)
    vi.spyOn(api, 'post').mockResolvedValue({ data: dataset })
    const admitted = await getAnalysisDataset('REGN', range)
    expect(admitted.series).toBe(dataset.series)
    expect(admitted).toEqual(sent)
  })

  it('leaves a dataset that carries none of the fields exactly as it was, an odd one included', () => {
    const plain = planted('no_evidence')
    const before = structuredClone(plain)
    expect(decodeLaterFilings(plain)).toBe(plain)
    expect(plain).toEqual(before)
    // Not this reader's to judge: the notes decoder and the page read the rest as they did.
    for (const odd of [{}, { series: null }, { series: [{ concept: 'revenue' }] }, { series: [{ points: [null] }] }]) {
      expect(decodeLaterFilings(odd as unknown as AnalysisDataset)).toBe(odd)
    }
  })

  it('admits the growth as first reported as a number, n/m where the own values change sign, or null where they give none', () => {
    for (const first of [0.1428, 'nm', null] as const) {
      const dataset = planted(REGN)
      pointOf(dataset, 'revenue', 'FY2018').yoy_first_reported = first
      expect(() => decodeLaterFilings(dataset)).not.toThrow()
    }
  })

  const refusals: Array<[string, (dataset: AnalysisDataset) => void]> = [
    ['a first-reported value that is not a number', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.value = '6710800000' as unknown as number }],
    ['a first-reported value equal to the one shown', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.value = 5_145_600_000 }],
    ['a first-reported value beside no value shown', (ds) => { pointOf(ds, 'revenue', 'FY2018').value = null }],
    ['a unit that is not the figure’s', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.unit = 'EUR' }],
    ['the shown filing’s accession as the own report’s', (ds) => { const point = pointOf(ds, 'revenue', 'FY2018'); point.first_reported!.accession = point.accession! }],
    ['an empty form', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.form = '' }],
    ['a filed day that does not exist', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.filed_at = '2019-02-30' }],
    ['a filed day in words', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.filed_at = '7 Feb 2019' }],
    ['a later filed day that is a timestamp', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.later_filed_at = '2021-02-08T00:00:00Z' }],
    ['a source link that is not a string', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.source_url = 42 as unknown as string }],
    ['a disagreement the page has no words for', (ds) => { (pointOf(ds, 'revenue', 'FY2018').first_reported as { disagreement: unknown }).disagreement = 'rounding' }],
    ['a sign flip the two values do not show', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.disagreement = 'opposite_sign' }],
    ['a factor of 1,000 the two values do not show', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.disagreement = 'scale' }],
    ['growth as first reported beside a growth that is not n/m', (ds) => { pointOf(ds, 'revenue', 'FY2018').yoy = -0.1237 }],
    ['growth as first reported that is neither a number, n/m nor null', (ds) => { pointOf(ds, 'revenue', 'FY2018').yoy_first_reported = '14.3%' as unknown as number }],
    ['an input’s first-reported value in another unit', (ds) => { pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1].first_reported!.unit = 'EUR' }],
    ['an input’s first-reported value equal to the input', (ds) => { pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1].first_reported!.value = 5_145_600_000 }],
  ]
  it.each(refusals)('refuses %s, so the page prints nothing false', async (_, edit) => {
    const dataset = planted(REGN)
    edit(dataset)
    expect(() => decodeLaterFilings(dataset)).toThrow(LaterFilingsRejection)
    vi.spyOn(api, 'post').mockResolvedValue({ data: dataset })
    await expect(getAnalysisDataset('REGN', range)).rejects.toBeInstanceOf(LaterFilingsRejection)
  })

  it('reads a sign flip and a factor of 1,000 from the two values, in either direction', () => {
    const dataset = planted(SIGN_AND_SCALE)
    expect(() => decodeLaterFilings(dataset)).not.toThrow()
    const debt = pointOf(dataset, 'long_term_debt', 'FY2019')
    // The own report's value 1,000,000 times larger than the one shown: a factor of 1,000², the other way.
    debt.first_reported!.value = debt.value! * 1_000_000
    expect(() => decodeLaterFilings(dataset)).not.toThrow()
    debt.first_reported!.value = debt.value! * 1_000 * -1
    expect(() => decodeLaterFilings(dataset)).toThrow(LaterFilingsRejection)
  })
})
