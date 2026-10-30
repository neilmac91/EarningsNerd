/* =============================================================================
   later-filings.spec.tsx — the page's reader of the later-filing evidence (MPA WP5a-F1)
   -----------------------------------------------------------------------------
   Where a later filing reports a value other than the one a fiscal year's own annual report gave, the producer
   (WP5a-B) will send the own report's value beside the shown one (`first_reported`) and, where a comparison reads n/m
   across the change, the growth as first reported (`yoy_first_reported`), in an annual run alone (D5; a quarterly run's
   evidence refuses the dataset until it lands with its reader). The page reads them before the producer
   writes them. The shared fixture (backend/tests/fixtures/analysis_later_filings.json) plants that wire shape on
   REGN's own-report values (WP5b) and holds the later-filing places both sides compute; the backend's twin of
   laterFilingPlaces reads the same cases when it lands.
============================================================================= */
import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import api from '@/lib/api/client'
import { getAnalysisDataset, type AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { decodeLaterFilings, laterFilingPlaces, LaterFilingsRejection, scaleSteps } from '@/features/analysis/lib/laterFilings'
import DataNotes from '@/features/analysis/components/DataNotes'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import KpiStrip from '@/features/analysis/components/KpiStrip'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import { buildToplineModel } from '@/features/analysis/lib/charts/model'
import { chartReadouts } from '@/features/analysis/lib/charts/readout'
import { resolveDataNotes } from '@/features/analysis/lib/dataNotes'

type Ref = { concept: string; label: string; period: string }
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
    ['an own report with no accession', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.accession = '' }],
    ['an empty form', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.form = '' }],
    ['a filed day that does not exist', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.filed_at = '2019-02-30' }],
    ['a filed day in words', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.filed_at = '7 Feb 2019' }],
    ['a later filed day that is a timestamp', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.later_filed_at = '2021-02-08T00:00:00Z' }],
    ['a source link that is not a string', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported!.source_url = 42 as unknown as string }],
    ['a disagreement the page has no words for', (ds) => { (pointOf(ds, 'revenue', 'FY2018').first_reported as { disagreement: unknown }).disagreement = 'rounding' }],
    // On total assets FY2018, which no growth as first reported crosses, so only the finding's own check can refuse it.
    ['a sign flip the two values do not show', (ds) => { pointOf(ds, 'total_assets', 'FY2018').first_reported!.disagreement = 'opposite_sign' }],
    ['a factor of 1,000 the two values do not show', (ds) => { pointOf(ds, 'total_assets', 'FY2018').first_reported!.disagreement = 'scale' }],
    ['growth as first reported beside a growth that is not n/m', (ds) => { pointOf(ds, 'revenue', 'FY2018').yoy = -0.1237 }],
    ['growth as first reported that is neither a number, n/m nor null', (ds) => { pointOf(ds, 'revenue', 'FY2018').yoy_first_reported = '14.3%' as unknown as number }],
    ['an input’s first-reported value in another unit', (ds) => { pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1].first_reported!.unit = 'EUR' }],
    ['an input’s first-reported value equal to the input', (ds) => { pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1].first_reported!.value = 5_145_600_000 }],
    // Reported figures only: a calculated figure's evidence sits on its inputs (item 5).
    ['a first-reported value on a calculated figure', (ds) => {
      const margin = pointOf(ds, 'net_margin', 'FY2018')
      margin.first_reported = { ...pointOf(ds, 'revenue', 'FY2018').first_reported!, value: 36.4248, unit: 'pure' }
    }],
    // An input carries evidence as a reported figure does: a calculated input's sits on its own inputs.
    ['a first-reported value on a calculated input', (ds) => {
      const revenue = pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1]
      revenue.provenance = { ...revenue.provenance!, method: 'calculated' }
    }],
    // Every place an input can sit is read: a growth's inputs, an input's own inputs, a window's inputs.
    ['a growth input’s first-reported value in another unit', (ds) => {
      pointOf(ds, 'revenue', 'FY2018').yoy_provenance!.inputs = [badInput()]
    }],
    ['a first-reported value in another unit two inputs deep', (ds) => {
      pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1].provenance = { ...pointOf(ds, 'net_margin', 'FY2018').provenance!, inputs: [badInput()] }
    }],
    ['a CAGR input’s first-reported value in another unit', (ds) => { seriesOf(ds, 'revenue').cagr_provenance!.inputs = [badInput()] }],
    ['a window change input’s first-reported value in another unit', (ds) => { seriesOf(ds, 'net_margin').window_pp_provenance!.inputs = [badInput()] }],
    // A QoQ carries none: a quarterly run has no evidence yet (D5), and an annual run no QoQ.
    ['a QoQ’s growth as first reported', (ds) => { Object.assign(pointOf(ds, 'revenue', 'FY2018'), { qoq: 'nm', qoq_first_reported: 0.1 }) }],
  ]
  it.each(refusals)('refuses %s, so the page prints nothing false', async (_, edit) => {
    const dataset = planted(REGN)
    edit(dataset)
    expect(() => decodeLaterFilings(dataset)).toThrow(LaterFilingsRejection)
    vi.spyOn(api, 'post').mockResolvedValue({ data: dataset })
    await expect(getAnalysisDataset('REGN', range)).rejects.toBeInstanceOf(LaterFilingsRejection)
  })

  /** An input of the shown revenue whose own report's value is in another unit: refused wherever the decoder reads it. */
  function badInput() {
    return { concept: 'revenue', value: 5_145_600_000, unit: 'USD', accession: '0001804220-21-000008',
      first_reported: { value: 6_710_800_000, unit: 'EUR', accession: '0001532176-19-000009', form: '10-K' } }
  }

  // Annual runs alone carry the evidence (D5): each field refuses a quarterly run, alone in an otherwise plain dataset.
  const quarterly: Array<[string, (dataset: AnalysisDataset) => void]> = [
    ['a figure’s first-reported value', (ds) => { pointOf(ds, 'revenue', 'FY2018').first_reported = planted(REGN).series[0].points[1].first_reported }],
    ['a growth as first reported', (ds) => { Object.assign(pointOf(ds, 'revenue', 'FY2018'), { yoy: 'nm', yoy_first_reported: 0.1428 }) }],
    ['an input’s first-reported value', (ds) => { pointOf(ds, 'net_margin', 'FY2018').provenance!.inputs[1].first_reported = planted(REGN).series[0].points[1].first_reported }],
    ['a QoQ’s growth as first reported', (ds) => { Object.assign(pointOf(ds, 'revenue', 'FY2018'), { qoq: 'nm', qoq_first_reported: 0.1 }) }],
  ]
  it.each(quarterly)('refuses %s in a quarterly run', (_, add) => {
    const dataset = withoutEvidence(planted(REGN))
    add(dataset)
    // The same field in an annual run is read (a QoQ's aside, which no run carries).
    if (!/QoQ/.test(_)) expect(() => decodeLaterFilings(dataset)).not.toThrow()
    expect(() => decodeLaterFilings({ ...dataset, mode: 'quarterly' })).toThrow(LaterFilingsRejection)
    expect(() => decodeLaterFilings({ ...withoutEvidence(planted(REGN)), mode: 'quarterly' })).not.toThrow()
  })

  it('refuses a growth as first reported other than n/m where a calculated figure’s input carries the finding, on its year or the year before', () => {
    // The shared fixture's margin, whose FY2019 revenue input carries a factor of 1,000, reads n/m on FY2019 and FY2020.
    expect(() => decodeLaterFilings(planted('a_margin_whose_input_carries_a_scale_finding'))).not.toThrow()
    for (const [period, first] of [['FY2019', -9.52], ['FY2020', 14.44], ['FY2020', null]] as const) {
      const dataset = planted('a_margin_whose_input_carries_a_scale_finding')
      pointOf(dataset, 'net_margin', period).yoy_first_reported = first
      expect(() => decodeLaterFilings(dataset), `${period} ${first}`).toThrow(LaterFilingsRejection)
    }
    // Two inputs deep counts as well.
    const deep = planted(REGN)
    const margin = pointOf(deep, 'net_margin', 'FY2018')
    const revenue = margin.provenance!.inputs[1]
    revenue.first_reported = null
    revenue.provenance = { ...margin.provenance!, inputs: [{ concept: 'revenue_part', value: 5_000, unit: 'USD', accession: 'a-1', first_reported: { value: 5, unit: 'USD', accession: 'a-0', disagreement: 'scale' } }] }
    expect(() => decodeLaterFilings(deep)).toThrow(/must be n\/m across a sign or scale finding/)
  })

  it('reads the calculated refusal off the figure’s own method, not its series’', () => {
    // A reported point in a series with a calculated point keeps its evidence.
    const mixed = planted(REGN)
    pointOf(mixed, 'revenue', 'FY2017').provenance = { ...pointOf(mixed, 'revenue', 'FY2017').provenance!, method: 'calculated' }
    expect(() => decodeLaterFilings(mixed)).not.toThrow()
    // A calculated point in a series of reported ones is refused.
    const calculated = planted(REGN)
    pointOf(calculated, 'revenue', 'FY2018').provenance = { ...pointOf(calculated, 'revenue', 'FY2018').provenance!, method: 'calculated' }
    expect(() => decodeLaterFilings(calculated)).toThrow(/sits on a calculated figure/)
  })

  it('refuses a period that is not a string beside a growth as first reported with its own rejection, never a TypeError', () => {
    const dataset = planted(REGN)
    pointOf(dataset, 'revenue', 'FY2018').period = 2018 as unknown as string
    expect(() => decodeLaterFilings(dataset)).toThrow(LaterFilingsRejection)
  })

  it('refuses a growth as first reported other than n/m across a sign or scale finding on either year', () => {
    expect(() => decodeLaterFilings(planted(SIGN_AND_SCALE))).not.toThrow()
    // Financing cash flow FY2020 carries the sign flip; Long-term debt FY2020's year before carries the factor of 1,000.
    for (const [concept, first] of [['financing_cash_flow', 0.5], ['long_term_debt', 1004.04], ['long_term_debt', null]] as const) {
      const dataset = planted(SIGN_AND_SCALE)
      pointOf(dataset, concept, 'FY2020').yoy_first_reported = first
      expect(() => decodeLaterFilings(dataset), `${concept} ${first}`).toThrow(LaterFilingsRejection)
    }
  })

  it('takes a factor of 1,000ⁿ only when exact, and n from 1 to 3 either way', () => {
    expect(scaleSteps(1, 1_000)).toBe(1)
    expect(scaleSteps(5_969_900, 5_969_900_000)).toBe(1)
    expect(scaleSteps(1, 1e6)).toBe(2)
    expect(scaleSteps(1, 1e9)).toBe(3)
    expect(scaleSteps(1e9, 1)).toBe(-3)
    expect(scaleSteps(-2, -2_000)).toBe(1)
    for (const [own, shown] of [[1, 999.9], [1, 1_001], [1, 999], [1, 1e12], [1e12, 1], [1, 1e15], [1, -1_000], [0, 1_000], [1, 1]]) {
      expect(scaleSteps(own, shown), `${own} → ${shown}`).toBeNull()
    }
    // The decoder holds a scale finding to it: 999.9 times the own value is no factor of 1,000.
    const dataset = planted(SIGN_AND_SCALE)
    const debt = pointOf(dataset, 'long_term_debt', 'FY2019')
    debt.first_reported!.value = debt.value! / 999.9
    expect(() => decodeLaterFilings(dataset)).toThrow(LaterFilingsRejection)
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

/** The metrics table on `dataset`, and the dialog the figure named `name` (its label, period and figure) opens. */
async function dialogFor(dataset: AnalysisDataset, name: RegExp) {
  render(<DataNotesProvider dataset={dataset}><MetricsTable dataset={dataset} /></DataNotesProvider>)
  await userEvent.click(screen.getByRole('button', { name }))
  return screen.getByRole('dialog')
}
const linkText = (dialog: HTMLElement) => within(dialog).queryAllByRole('link').map((link) => link.textContent)

describe('the evidence dialog gives both filings (D11)', () => {
  it('states the year’s own annual report’s value, then the later filing’s, the one shown, with a link to each', async () => {
    const dialog = await dialogFor(planted(REGN), /^Revenue, FY2018: \$5\.1B/)
    expect(within(dialog).getByRole('heading', { name: 'Source filings' })).toBeInTheDocument()
    expect(dialog).toHaveTextContent('First reported as $6.7B in its own annual report (10-K, filed 7 Feb 2019). A later filing (filed 8 Feb 2021) reports $5.1B, shown here.')
    // Both values as filed, exactly, in the figure face, each a label and a value that takes the row's right edge.
    const rows = [...dialog.querySelectorAll('p')].filter((row) => row.textContent?.startsWith('As filed'))
    expect(rows.map((row) => row.textContent)).toEqual(['As filed in its own annual report: 6,710,800,000 USD', 'As filed in the later filing: 5,145,600,000 USD'])
    expect(rows[0].parentElement).toHaveClass('font-figure', 'tabular-nums', 'lining-nums')
    // A value that wraps within itself (320px under 200% text) keeps the edge: right-aligned text.
    expect(rows.map((row) => row.lastElementChild?.className)).toEqual(['ml-auto text-right', 'ml-auto text-right'])
    // Two links, each named for its filing: the visible words carry no figure (brand rule 2), the name adds form and day.
    expect(linkText(dialog)).toEqual(['Open its own annual report on SEC.gov', 'Open the later filing on SEC.gov'])
    expect(linkText(dialog).join(' ')).not.toMatch(/\d/)
    const ownLink = within(dialog).getByRole('link', { name: 'Open its own annual report on SEC.gov (10-K, filed 7 Feb 2019) for Revenue, FY2018' })
    expect(ownLink).toHaveAttribute('href', 'https://www.sec.gov/Archives/edgar/data/872589/000153217619000009/')
    const shownLink = within(dialog).getByRole('link', { name: 'Open the later filing on SEC.gov (10-K, filed 8 Feb 2021) for Revenue, FY2018' })
    expect(shownLink).toHaveAttribute('href', 'https://www.sec.gov/Archives/edgar/data/872589/000180422021000008/')
    expect(dialog).toHaveTextContent('Filing 0001532176-19-000009')
    expect(dialog).toHaveTextContent('Filing 0001804220-21-000008')
    // Evidence, not a note (D-061): the checks passed, and no letter or warning ink.
    expect(dialog).toHaveTextContent('Automated checks passed')
    expect(dialog.querySelector('[data-note-letter]')).toBeNull()
    expect(dialog.querySelector('[class*="text-warning"]')).toBeNull()
  })

  it('keeps a figure without evidence exactly as it was: one filing, one link', async () => {
    const dialog = await dialogFor(planted(REGN), /^Revenue, FY2017: /)
    expect(within(dialog).getByRole('heading', { name: 'Source filing' })).toBeInTheDocument()
    expect(dialog).not.toHaveTextContent(/First reported|As filed|later filing/)
    expect(linkText(dialog)).toEqual(['Open original SEC filing'])
    expect(within(dialog).getByRole('link', { name: 'Open original SEC filing for Revenue, FY2017' })).toBeInTheDocument()
  })

  it('leaves out each part the payload does not carry, never inventing a form or a day', async () => {
    const dataset = planted(REGN)
    Object.assign(pointOf(dataset, 'revenue', 'FY2018').first_reported!, { form: null, filed_at: null, later_filed_at: null })
    const dialog = await dialogFor(dataset, /^Revenue, FY2018: /)
    expect(dialog).toHaveTextContent('First reported as $6.7B in its own annual report. A later filing reports $5.1B, shown here.')
    expect(dialog).not.toHaveTextContent(/undefined|null|Invalid|filed \(|\(\)/)
    expect(within(dialog).getByRole('link', { name: 'Open its own annual report on SEC.gov for Revenue, FY2018' })).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Open the later filing on SEC.gov (10-K) for Revenue, FY2018' })).toBeInTheDocument()
  })

  it.each([
    ['http://www.sec.gov/Archives/edgar/data/872589/000153217619000009/'],
    ['https://example.com/Archives/edgar/data/872589/000153217619000009/'],
    ['javascript:alert(1)'],
  ])('draws no link to the own report from a source that is not https on SEC.gov: %s', async (url) => {
    const dataset = planted(REGN)
    pointOf(dataset, 'revenue', 'FY2018').first_reported!.source_url = url
    const dialog = await dialogFor(dataset, /^Revenue, FY2018: /)
    expect(linkText(dialog)).toEqual(['Open the later filing on SEC.gov'])
    expect(dialog.querySelector(`a[href="${url}"]`)).toBeNull()
    // The sentence and the own report's accession stand.
    expect(dialog).toHaveTextContent('First reported as $6.7B in its own annual report')
    expect(dialog).toHaveTextContent('Filing 0001532176-19-000009')
  })

  it('names a 20-F or an amendment as its form, and a filed day without a form', async () => {
    const dataset = planted(REGN)
    Object.assign(pointOf(dataset, 'revenue', 'FY2018').first_reported!, { form: '10-K/A' })
    Object.assign(pointOf(dataset, 'revenue', 'FY2019').first_reported!, { form: null })
    expect(await dialogFor(dataset, /^Revenue, FY2018: /)).toHaveTextContent('in its own annual report (10-K/A, filed 7 Feb 2019).')
    cleanup()
    expect(await dialogFor(dataset, /^Revenue, FY2019: /)).toHaveTextContent('First reported as $7.9B in its own annual report (filed 7 Feb 2020). A later filing (filed 7 Feb 2022) reports $6.6B, shown here.')
  })

  it('prints two values that round alike with the decimals that tell them apart', async () => {
    const dialog = await dialogFor(planted(REGN), /^Total assets, FY2018: /)
    expect(dialog).toHaveTextContent('First reported as $15.16B in its own annual report (10-K, filed 7 Feb 2019). A later filing (filed 7 Feb 2020) reports $15.20B, shown here.')
  })

  it('says what an exact comparison found, from the two values: the opposite sign, or the factor and its direction', async () => {
    const dataset = planted(SIGN_AND_SCALE)
    const flip = await dialogFor(dataset, /^Financing cash flow, FY2020: /)
    expect(within(flip).getByText('First reported as $1.9B in its own annual report (10-K, filed 8 Feb 2021). A later filing (filed 7 Feb 2022) reports -$1.9B, shown here.')).toBeInTheDocument()
    expect(within(flip).getByText('A later filing reports the opposite sign.')).toBeInTheDocument()
    // The finding is also a note (source_conflict), which marks the figure as any such note does.
    expect(flip).toHaveTextContent('Needs review · Note a')
    cleanup()
    const larger = await dialogFor(dataset, /^Long-term debt, FY2019: /)
    expect(larger).toHaveTextContent('First reported as $6.0M in its own annual report (10-K, filed 7 Feb 2020). A later filing (filed 8 Feb 2021) reports $6.0B, shown here.')
    expect(within(larger).getByText('A later filing reports a value 1,000 times larger than the year’s own annual report.')).toBeInTheDocument()
    cleanup()
    const smaller = planted(SIGN_AND_SCALE)
    const debt = pointOf(smaller, 'long_term_debt', 'FY2019')
    debt.first_reported!.value = debt.value! * 1_000_000
    expect(within(await dialogFor(smaller, /^Long-term debt, FY2019: /)).getByText('A later filing reports a value 1,000,000 times smaller than the year’s own annual report.')).toBeInTheDocument()
  })

  it('shows a calculated figure’s input evidence where its input carries it (item 5), and counts no letter for it', async () => {
    const dialog = await dialogFor(planted(REGN), /^Net margin, FY2018: /)
    const inputs = within(dialog).getAllByRole('listitem')
    const revenue = inputs.find((item) => /^revenue/i.test(item.textContent ?? ''))!
    expect(revenue).toHaveTextContent('First reported as $6.7B in its own annual report (10-K, filed 7 Feb 2019). A later filing (filed 8 Feb 2021) reports $5.1B, shown here.')
    expect(within(revenue).getByRole('link', { name: 'Open its own annual report on SEC.gov (10-K, filed 7 Feb 2019) for revenue, 2018-01-01 to 2018-12-31' })).toBeInTheDocument()
    expect(within(revenue).getByRole('link', { name: 'Open the later filing on SEC.gov (filed 8 Feb 2021) for revenue, 2018-01-01 to 2018-12-31' })).toBeInTheDocument()
    const netIncome = inputs.find((item) => /^net income/i.test(item.textContent ?? ''))!
    expect(netIncome).not.toHaveTextContent('First reported')
    expect(within(netIncome).getByRole('link', { name: /^Open original SEC filing for net income/ })).toBeInTheDocument()
    expect(dialog.querySelector('[data-note-letter]')).toBeNull()
  })
})

/** The comparison section of an open evidence dialog. */
const comparisonOf = (dialog: HTMLElement) => within(dialog).getByRole('heading', { name: /comparison$/ }).closest('section')!
const CAUSE = 'Not meaningful: a later filing reports a different value for one or both of the two years.'

describe('a basis n/m says its cause (D12)', () => {
  it('in the dialog: the cause, then the growth as first reported, a sign change’s n/m keeping no such sentence', async () => {
    const dataset = planted(REGN)
    const fy2018 = comparisonOf(await dialogFor(dataset, /^Revenue, FY2018: /))
    expect(fy2018).toHaveTextContent(`YoY comparisonn/mnot meaningful${CAUSE}As first reported: +14.3%`)
    // The calculation passed and says so; the cause stands above it.
    expect(fy2018).toHaveTextContent('Automated checks passed')
    cleanup()
    // FY2020's own value is the one shown, but its prior year's is not: the growth still crosses the change.
    expect(comparisonOf(await dialogFor(dataset, /^Revenue, FY2020: /))).toHaveTextContent(`${CAUSE}As first reported: +8.1%`)
    cleanup()
    // A margin's change is in percentage points, as first reported too.
    expect(comparisonOf(await dialogFor(dataset, /^Net margin, FY2018: /))).toHaveTextContent(`${CAUSE}As first reported: +16.0pp`)
    cleanup()
    // An n/m with no growth as first reported is a sign change's: no cause sentence of this kind.
    delete pointOf(dataset, 'revenue', 'FY2018').yoy_first_reported
    const signChange = comparisonOf(await dialogFor(dataset, /^Revenue, FY2018: /))
    expect(signChange).toHaveTextContent('n/m')
    expect(signChange).not.toHaveTextContent(/later filing|As first reported/)
  })

  it('in the dialog: own reports that give no growth leave the cause alone; values of opposite signs give n/m, read in words', async () => {
    const dataset = planted(REGN)
    pointOf(dataset, 'revenue', 'FY2018').yoy_first_reported = null
    const none = comparisonOf(await dialogFor(dataset, /^Revenue, FY2018: /))
    expect(none).toHaveTextContent(CAUSE)
    expect(none).not.toHaveTextContent('As first reported')
    cleanup()
    const flip = comparisonOf(await dialogFor(planted(SIGN_AND_SCALE), /^Financing cash flow, FY2020: /))
    expect(flip).toHaveTextContent(`${CAUSE}As first reported: n/mnot meaningful`)
    expect(within(flip).getAllByText('not meaningful').every((words) => words.classList.contains('sr-only'))).toBe(true)
  })

  it('keeps the table legend, and an annual card’s window growth carries no cause (D5)', async () => {
    const dataset = planted(REGN)
    const { container } = render(<DataNotesProvider dataset={dataset}><KpiStrip dataset={dataset} /><MetricsTable dataset={dataset} /></DataNotesProvider>)
    expect(container).toHaveTextContent('n/m means not meaningful.')
    await userEvent.click(within(container.querySelector('[data-analysis-kpi]') as HTMLElement).getByRole('button'))
    expect(screen.getByRole('dialog')).not.toHaveTextContent(/one or both/)
  })

  it('where the shown values change sign and the basis changed too, the later-filing cause wins everywhere', async () => {
    // Revenue FY2018 shown below zero: FY2018's and FY2019's YoY read n/m for the sign alone, and each still carries its
    // growth as first reported, as the producer sends it where the basis changed too.
    const dataset = planted(REGN)
    pointOf(dataset, 'revenue', 'FY2018').value = -5_145_600_000
    expect(() => decodeLaterFilings(dataset)).not.toThrow()
    const model = buildToplineModel(dataset, resolveDataNotes(dataset))
    expect(model.footnotes.filter((footnote) => footnote.mark === 'n/m')).toEqual([
      { mark: 'n/m', text: 'Not meaningful: a later filing reports a different value for one or both years (FY2018–FY2020).' },
    ])
    expect(laterFilingPlaces(dataset).comparisons.filter((ref) => ref.concept === 'revenue').map((ref) => ref.period)).toEqual(['FY2018', 'FY2019', 'FY2020'])
    // The rendered line too, so a filter inside DataNotes cannot drop the sign-changed years.
    const { container } = render(<DataNotes dataset={dataset} />)
    expect(container.querySelector(LINE)!.textContent).toContain('Growth across the change reads n/m (Revenue FY2018, FY2019, FY2020;')
    cleanup()
    const fy2019 = comparisonOf(await dialogFor(dataset, /^Revenue, FY2019: /))
    expect(fy2019).toHaveTextContent(`${CAUSE}As first reported: +17.2%`)
  })

  it('in the table: a QoQ cell’s dialog never takes a YoY’s cause', async () => {
    // Undecoded, so the table alone is tried: a quarterly cell compares QoQ where its QoQ is a number.
    const quarterly: AnalysisDataset = {
      ...planted('no_evidence'), mode: 'quarterly', period_key: '2025Q2',
      periods: [{ key: '2025Q2', fiscal_year: 2025, fiscal_period: 'Q2', period_end: '2025-06-30' }],
      series: [{ concept: 'revenue', label: 'Revenue', unit: 'USD', percent: false, cagr: null, points: [
        { period: '2025Q2', value: 4_000_000_000, unit: 'USD', qoq: 0.05, yoy: 'nm', yoy_first_reported: 0.1 },
      ] }],
    }
    const qoq = comparisonOf(await dialogFor(quarterly, /^Revenue, Q2 2025: /))
    expect(qoq).toHaveTextContent('QoQ comparison+5.0%')
    expect(qoq).not.toHaveTextContent(/later filing|As first reported/)
  })

  it('in the dialog: no growth as first reported across a sign or scale finding, only n/m', async () => {
    // A margin whose year-before revenue input carries the finding says n/m too.
    const margin = comparisonOf(await dialogFor(planted('a_margin_whose_input_carries_a_scale_finding'), /^Net margin, FY2020: /))
    expect(margin).toHaveTextContent(`${CAUSE}As first reported: n/mnot meaningful`)
    cleanup()
    // Long-term debt FY2020's year before carries a factor of 1,000: the growth from its own report would measure the
    // slip, so it reads n/m.
    const debt = comparisonOf(await dialogFor(planted(SIGN_AND_SCALE), /^Long-term debt, FY2020: /))
    expect(debt).toHaveTextContent(`${CAUSE}As first reported: n/mnot meaningful`)
    expect(debt).not.toHaveTextContent('%')
  })

  it('in the chart: a footnote line of its own for those periods, never the sign change’s, no letter, the tooltip as it was', () => {
    const dataset = planted(REGN)
    const notes = resolveDataNotes(dataset)
    const model = buildToplineModel(dataset, notes)
    const growth = model.panels[1].marks[0].points
    expect(growth.filter((point) => point.nm).map((point) => point.period)).toEqual(['FY2018', 'FY2019', 'FY2020'])
    expect(model.footnotes).toContainEqual({ mark: 'n/m', text: 'Not meaningful: a later filing reports a different value for one or both years (FY2018–FY2020).' })
    expect(model.footnotes.map((footnote) => footnote.text).join(' ')).not.toMatch(/zero or of the opposite sign/)
    expect(model.notesBand).toBeNull()
    const fy2018 = chartReadouts(model, dataset, notes).find((period) => period.period === 'FY2018')!
    expect(fy2018.rows.find((row) => row.label === 'YoY growth')!.text).toBe('n/m · not meaningful')
  })
})

/** Every figure, comparison and input with its later-filing fields gone: the run as the page read it before WP5a. */
function withoutEvidence(dataset: AnalysisDataset): AnalysisDataset {
  const plain = structuredClone(dataset)
  const strip = (input: { first_reported?: unknown; provenance?: { inputs: unknown[] } | null }) => {
    delete input.first_reported
    input.provenance?.inputs.forEach((operand) => strip(operand as typeof input))
  }
  for (const series of plain.series) for (const point of series.points) {
    strip(point)
    delete point.yoy_first_reported
  }
  return plain
}
const LINE = '[data-analysis-later-filings]'

describe('the data notes’ later-filing line (D8)', () => {
  it.each(CASES.map((entry) => [entry.name, entry]))('finds the places the shared fixture holds: %s', (_, entry) => {
    expect(laterFilingPlaces(entry.dataset)).toEqual(entry.expected)
  })

  it('names the reported figures in the open detail, after the notes, and the growths that read n/m across the change', () => {
    const dataset = planted(REGN)
    const { container } = render(<DataNotes dataset={dataset} />)
    const line = container.querySelector(LINE)!
    // Total assets FY2018's 0.24% gap moved no growth past the n/m rule: a figure of the first sentence, never the second's.
    expect(line.textContent).toBe('A later filing reports a different value for 3 figures (Revenue FY2018, FY2019; Total assets FY2018); select one to see both filings. Growth across the change reads n/m (Revenue FY2018, FY2019, FY2020; Net margin FY2018, FY2019, FY2020).')
    // In the open detail, after the notes list and before the legend, never in the closed summary.
    const detail = container.querySelector('[data-analysis-data-notes] > details > div')!
    expect(line.parentElement).toBe(detail)
    expect(line.previousElementSibling?.tagName).toBe('UL')
    expect(line.nextElementSibling?.textContent).toMatch(/^Select any figure to see its source filing/)
    expect(container.querySelector('[data-analysis-data-notes] > details > summary')!.querySelector(LINE)).toBeNull()
  })

  it('leaves the closed summary as it was, “No figures need review” included (D7), and draws no line without evidence', () => {
    const dataset = planted(REGN)
    const summary = (input: AnalysisDataset) => {
      const { container, unmount } = render(<DataNotes dataset={input} />)
      const text = container.querySelector('[data-analysis-data-notes] > details > summary')!.textContent
      const line = container.querySelector(LINE)
      unmount()
      return { text, line }
    }
    const before = summary(withoutEvidence(dataset))
    const after = summary(dataset)
    expect(after.text).toBe(before.text)
    expect(after.text).toMatch(/No figures need review · \d+ checked/)
    expect(before.line).toBeNull()
    expect(summary(planted('no_evidence')).line).toBeNull()
  })

  it('drops the n/m sentence where no growth reads n/m across the change, a sign change’s n/m included, and counts one figure as one', () => {
    const { container } = render(<DataNotes dataset={planted('evidence_with_no_change_of_basis')} />)
    expect(container.querySelector(LINE)!.textContent).toBe('A later filing reports a different value for 1 figure (Total assets FY2018); select one to see both filings.')
    cleanup()
    // Net income's n/m here comes from a change of sign, which carries no growth as first reported: not the line's.
    const { container: signChange } = render(<DataNotes dataset={planted('a_sign_change_n_m_is_no_change_of_basis')} />)
    expect(signChange.querySelector(LINE)!.textContent).toBe('A later filing reports a different value for 1 figure (Total assets FY2018); select one to see both filings.')
    cleanup()
    // With every growth as first reported taken away, the REGN run keeps its figures and loses the sentence.
    const regn = planted(REGN)
    for (const series of regn.series) for (const point of series.points) delete point.yoy_first_reported
    const { container: none } = render(<DataNotes dataset={regn} />)
    expect(none.querySelector(LINE)!.textContent).toBe('A later filing reports a different value for 3 figures (Revenue FY2018, FY2019; Total assets FY2018); select one to see both filings.')
    cleanup()
    // The exact sign flip and the factor of 1,000 are figures of the line too, beside their note (D8).
    const { container: flipped } = render(<DataNotes dataset={planted(SIGN_AND_SCALE)} />)
    expect(flipped.querySelector(LINE)!.textContent).toBe('A later filing reports a different value for 2 figures (Financing cash flow FY2020; Long-term debt FY2019); select one to see both filings. Growth across the change reads n/m (Financing cash flow FY2020; Long-term debt FY2020).')
  })

  it.each(CASES.map((entry) => [entry.name, entry]))('names in its n/m sentence exactly the comparisons that read n/m across the change: %s', (_, entry) => {
    // The places as the fixture lists them, grouped by metric in order here, apart from the page's own helper.
    const grouped = (refs: Ref[]) => {
      const byLabel = new Map<string, string[]>()
      for (const ref of refs) byLabel.set(ref.label, [...new Set([...(byLabel.get(ref.label) ?? []), ref.period])])
      return [...byLabel].map(([label, periods]) => `${label} ${periods.join(', ')}`).join('; ')
    }
    const { container } = render(<DataNotes dataset={structuredClone(entry.dataset)} />)
    const text = container.querySelector(LINE)?.textContent ?? null
    if (!entry.expected.values.length) return expect(text).toBeNull()
    const sentence = /Growth across the change reads n\/m \(([^)]*)\)\./.exec(text!)
    if (!entry.expected.comparisons.length) {
      expect(text).not.toMatch(/Growth across the change/)
      return
    }
    expect(sentence?.[1]).toBe(grouped(entry.expected.comparisons))
    // A figure with evidence whose own growth did not turn n/m is never named there.
    const changed = new Set(entry.expected.comparisons.map((ref) => `${ref.label} ${ref.period}`))
    for (const ref of entry.expected.values.filter((value) => !changed.has(`${value.label} ${value.period}`))) {
      expect(sentence![1].split('; ').some((place) => place.startsWith(`${ref.label} `) && place.slice(ref.label.length + 1).split(', ').includes(ref.period)), `${ref.label} ${ref.period}`).toBe(false)
    }
  })

  it('keeps its promise: every place it lists opens a dialog that gives both filings', async () => {
    for (const entry of CASES) {
      for (const ref of entry.expected.values) {
        const dialog = await dialogFor(structuredClone(entry.dataset), new RegExp(`^${ref.label}, ${ref.period}: `))
        expect(dialog, `${entry.name}: ${ref.label} ${ref.period}`).toHaveTextContent('First reported as')
        expect(within(dialog).getByRole('link', { name: /^Open its own annual report on SEC\.gov/ })).toBeInTheDocument()
        cleanup()
      }
    }
  })
})
