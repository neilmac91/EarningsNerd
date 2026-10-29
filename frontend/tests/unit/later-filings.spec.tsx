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
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import api from '@/lib/api/client'
import { getAnalysisDataset, type AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { decodeLaterFilings, LaterFilingsRejection } from '@/features/analysis/lib/laterFilings'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import MetricsTable from '@/features/analysis/components/MetricsTable'

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
    // Both values as filed, exactly, in the figure face.
    const own = within(dialog).getByText('As filed in its own annual report: 6,710,800,000 USD')
    expect(own).toBeInTheDocument()
    expect(own.parentElement).toHaveClass('font-figure', 'tabular-nums', 'lining-nums')
    expect(within(dialog).getByText('As filed in the later filing: 5,145,600,000 USD')).toBeInTheDocument()
    // Two links, each named for its filing: the visible words carry no figure (brand rule 2), the name adds form and day.
    expect(linkText(dialog)).toEqual(['Open its own annual report on SEC.gov', 'Open the filing shown on SEC.gov'])
    expect(linkText(dialog).join(' ')).not.toMatch(/\d/)
    const ownLink = within(dialog).getByRole('link', { name: 'Open its own annual report on SEC.gov (10-K, filed 7 Feb 2019) for Revenue, FY2018' })
    expect(ownLink).toHaveAttribute('href', 'https://www.sec.gov/Archives/edgar/data/872589/000153217619000009/')
    const shownLink = within(dialog).getByRole('link', { name: 'Open the filing shown on SEC.gov (10-K, filed 8 Feb 2021) for Revenue, FY2018' })
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
    expect(within(dialog).getByRole('link', { name: 'Open the filing shown on SEC.gov (10-K) for Revenue, FY2018' })).toBeInTheDocument()
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
    expect(within(revenue).getByRole('link', { name: 'Open the filing shown on SEC.gov (filed 8 Feb 2021) for revenue, 2018-01-01 to 2018-12-31' })).toBeInTheDocument()
    const netIncome = inputs.find((item) => /^net income/i.test(item.textContent ?? ''))!
    expect(netIncome).not.toHaveTextContent('First reported')
    expect(within(netIncome).getByRole('link', { name: /^Open original SEC filing for net income/ })).toBeInTheDocument()
    expect(dialog.querySelector('[data-note-letter]')).toBeNull()
  })
})
