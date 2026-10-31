/* =============================================================================
   sector-peers.spec.tsx: the company page's Sector peers panel (E251; features/peers)
   -----------------------------------------------------------------------------
   The panel on the peers fixture (tests/unit/fixtures/peers-cohorts.json, which
   backend/tests/unit/test_peers_fixture_contract.py holds to the service), its read answered here, rendered as the page
   renders it: the gate (SectorPeers) reads the default metric and loads the card only for a cohort.
   - E251's gaps, each a gate: a bank's label is the answer's `concept` (asked for revenue, it answers net interest
     income, and the first option, the plot's name, the rank line, the footnote and the readout all say so); no chart of
     0 or 1 bars, and none without the subject's own figure or of a metric it cannot name (each of cohort.ts noCohort's
     reasons alone renders nothing and the card never mounts, whatever `peer_count` says); the rank's denominator is the
     companies with a value, never `peer_count`.
   - Its behaviour: every cohort the panel shows (chartPlan.ts PEER_SHOWING, pinned by name) draws the subject in
     chart-1 and every other company in the context ink, in both themes; the chart draws every company its eleven slots
     hold (a cohort of eleven or fewer whole, the spread's eleventh among them), and a larger one the top eleven where the
     subject ranks among them, else the top ten and the subject, either side of the slots' edge, never parting a tie,
     the footnote saying what the chart shows, and nothing where it shows every company; the values stop starts at the
     subject and says who it is; a CNY cohort prints its axis and values in CNY and the footnote names it; the footnote
     names a drawn value that needs a source check; the picker offers the nine metrics FEATURED names at one width; a
     metric picked holds the plot's room and the rank line's while it loads, and says in the plot's place why its
     answer draws no chart or that its read failed.
   The engine's drawing is its own gate's (trend-charts-v2.spec.tsx, over these cohorts through the panel's builder),
   the tooltip swatch among it; the mount, the key and the boundary are company-sector-peers-mount.spec.tsx's, and the
   page as CI ships it tests/e2e/company-sector-peers.spec.ts's and company-first-load.spec.ts's.
============================================================================= */
import { readFileSync } from 'node:fs'
import type { ComponentProps } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const getPeers = vi.fn()
vi.mock('@/features/peers/api/peers-api', () => ({ getPeers: (...args: unknown[]) => getPeers(...args) }))
// The card, counted as it renders, so a case can say it never mounted.
const card = vi.hoisted(() => ({ renders: 0 }))
vi.mock('@/features/peers/components/SectorPeersCard', async (importOriginal) => {
  const { default: Card } = await importOriginal<typeof import('@/features/peers/components/SectorPeersCard')>()
  return {
    default: (props: ComponentProps<typeof Card>) => {
      card.renders += 1
      return <Card {...props} />
    },
  }
})

import { ThemeContext } from '@/components/ThemeProvider'
import { CHART_TOKENS } from '@/features/analysis/lib/charts/theme'
import type { PeerComparisonResponse } from '@/features/peers/api/peers-api'
import SectorPeers from '@/features/peers/components/SectorPeers'
import { drawn, noCohort } from '@/features/peers/lib/cohort'
import { peerChartDef } from '@/features/peers/lib/peerChart'
import { PEER_SHOWING, type PeerFixture } from './chartPlan'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/peers-cohorts.json', 'utf8')) as PeerFixture
const answerOf = (name: string): PeerComparisonResponse => structuredClone(FIXTURE.cases[name].response)
/** Every cohort the panel shows, by the pinned list (chartPlan.ts PEER_SHOWING), read as it stands rather than through
 *  peerBarCases, whose check of `shows` would stop this file's collection: here a case `shows` gets wrong fails as that
 *  case, below. */
const SHOWING = PEER_SHOWING
/** The CNY cohort as the engine prints it: CN¥ before every amount, never "$" (features/analysis/lib/charts/scale.ts
 *  moneyPrefix). */
const CNY_TICKS = ['CN¥0', 'CN¥200B', 'CN¥400B', 'CN¥600B', 'CN¥800B']
const CNY_LABELS = ['CN¥612B', 'CN¥480B', 'CN¥96B', 'CN¥41B']
const CNY_READOUT = /, CNYB, this company, rank 2 of 4, FY2025, year ended December 31, 2025\. Revenue: CN¥480\.1 billion\.$/
/** Every case it does not show, with the first reason it does not (cohort.ts noCohort), each reason alone deciding
 *  one at least: production's single and a withheld peer only that fewer than two companies have a figure; a subject
 *  with no fact or a withheld one beside companies with a value only the subject's own figure; capital expenditures
 *  only the metric the panel cannot name. Capital expenditures with no subject fact fails two, and its reason is the
 *  first in noCohort's order, the metric. */
const NOT_SHOWING = {
  'production single': 'few', 'no facts': 'subject', 'no fact, with peers': 'subject', 'no gross profit, with peers': 'subject',
  'withheld peer': 'few', 'withheld subject': 'subject', 'withheld subject, with peers': 'subject', 'capital expenditures': 'concept',
  'capital expenditures, no subject fact': 'concept',
} as const

// The card's module, the engine with it, loads once before the cases, as its chunk loads once a page: the first
// dynamic import transforms the engine, which under a full suite's load outlasts a find's default wait.
beforeAll(async () => {
  await import('@/features/peers/components/SectorPeersCard')
})

afterEach(() => {
  getPeers.mockReset()
  card.renders = 0
})

/** The panel on its page's ticker, its read answered by metric: an answer, or a promise of one. */
function renderPanel(answers: Record<string, PeerComparisonResponse | Promise<PeerComparisonResponse>>, { theme }: { theme?: 'light' | 'dark' } = {}) {
  getPeers.mockImplementation((_ticker: string, metric: string) => (metric in answers ? Promise.resolve(answers[metric]) : Promise.reject(new Error(`no answer for ${metric}`))))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const panel = (
    <QueryClientProvider client={client}>
      <SectorPeers ticker="TEST" />
    </QueryClientProvider>
  )
  return render(theme ? <ThemeContext.Provider value={{ theme, toggleTheme: () => {} }}>{panel}</ThemeContext.Provider> : panel)
}

/** The card, once the gate has loaded it: its section, named by its heading. */
const panelCard = async () => (await screen.findByRole('heading', { level: 2, name: 'Sector peers' }, { timeout: 4000 })).closest('section') as HTMLElement
const picker = (scope: HTMLElement) => within(scope).getByRole('combobox', { name: 'Metric' }) as HTMLSelectElement
/** The plot's drawing, once its font wait is over (jsdom has no Font Loading API, so it paints at once). */
const plotOf = async (scope: HTMLElement, label: string) => {
  const svg = await within(scope).findByRole('img', { name: `${label} chart` })
  return { svg, bars: [...svg.querySelectorAll('rect[data-series]')] }
}
/** The card on a case: a case on the default metric as the default answer; any other as the metric picked, the default
 *  answered with the spread, as a reader reaches it. */
async function openOn(name: string, options: { theme?: 'light' | 'dark' } = {}) {
  const { metric, response } = FIXTURE.cases[name]
  renderPanel(metric === 'revenue' ? { revenue: structuredClone(response) } : { revenue: answerOf('spread'), [metric]: structuredClone(response) }, options)
  const section = await panelCard()
  if (metric !== 'revenue') fireEvent.change(picker(section), { target: { value: metric } })
  return section
}
/** The line under the plot. */
const footnote = (scope: HTMLElement) => within(scope).getByText(/^Companies with the same SEC industry code/)
/** What follows the heading: the rank line, or the room held for it while a metric picked has none. */
const rankLine = (scope: HTMLElement) => scope.querySelector('h2')!.nextElementSibling as HTMLElement
/** The line in the plot's place, once there is one. */
const inPlace = (scope: HTMLElement) => waitFor(() => {
  const place = scope.querySelector<HTMLElement>('[data-chart-text="unavailable"]')
  expect(place, 'a line in the plot’s place').not.toBeNull()
  return place!
})
/** The default metric's answer has landed and settled. */
async function settle() {
  await waitFor(() => expect(getPeers).toHaveBeenCalled())
  await act(async () => {
    await getPeers.mock.results[0].value.catch(() => {})
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

describe('the Sector peers panel (E251)', () => {
  describe.each(SHOWING)('%s', (name) => {
    it.each(['light', 'dark'] as const)('%s: the card and its plot, named for the metric the answer ranks on, the subject in chart-1 and every other company in the context ink', async (theme) => {
      const answer = answerOf(name)
      const def = peerChartDef(answer)
      const section = await openOn(name, { theme })
      const { bars } = await plotOf(section, def.title)
      const tokens = CHART_TOKENS[theme]
      expect(bars, 'a bar a company drawn').toHaveLength(drawn(answer).length)
      for (const bar of bars) {
        const subject = bar.getAttribute('data-period') === def.start
        expect(bar.getAttribute('fill'), `${bar.getAttribute('data-period')}`).toBe(subject ? tokens.series[0] : tokens.context)
      }
      expect(bars.filter((bar) => bar.getAttribute('data-period') === def.start), 'the subject’s one bar').toHaveLength(1)
    })
  })

  it('reads a bank’s label from the answer’s concept: asked for revenue, it answers net interest income, and the picker, the plot, the rank line, the footnote and the readout all say so', async () => {
    renderPanel({ revenue: answerOf('bank') })
    const section = await panelCard()
    expect(getPeers).toHaveBeenCalledWith('TEST', 'revenue')
    const first = picker(section).options[0]
    expect([first.value, first.textContent, picker(section).value]).toEqual(['revenue', 'Net interest income', 'revenue'])
    await plotOf(section, 'Net interest income')
    expect(within(section).getByText(/ranks #/).closest('p')).toHaveTextContent('BNKB ranks #2 of 3 on net interest income')
    expect(footnote(section)).toHaveTextContent('each with its most recent annual net interest income from SEC filings (XBRL).')
    const stop = within(section).getByRole('slider', { name: 'Net interest income chart values' })
    expect(stop.getAttribute('aria-valuetext')).toMatch(/\. Net interest income: \$13\.60 billion\.$/)
    expect(section).not.toHaveTextContent(/revenue/i)
  })

  it('names, for every case it does not show, the first reason it does not, and none for a case it shows', () => {
    const cases = Object.keys(FIXTURE.cases)
    expect(Object.fromEntries(cases.filter((name) => !SHOWING.includes(name)).map((name) => [name, noCohort(answerOf(name))]))).toEqual(NOT_SHOWING)
    expect(SHOWING.filter((name) => noCohort(answerOf(name)) != null)).toEqual([])
  })

  // The builder refuses what the gate keeps out, so no chart draws without its subject or its metric's name (the refusal
  // the engine's sweeps held before the builder, E251's PR 1).
  it('builds no chart whose subject draws no bar, nor one on a metric FEATURED does not name', () => {
    expect(() => peerChartDef(answerOf('no fact, with peers'))).toThrow('peerChartDef: the subject NFWP draws no bar on revenue')
    expect(() => peerChartDef(answerOf('withheld subject, with peers'))).toThrow('peerChartDef: the subject WSPX draws no bar on eps_diluted')
    expect(() => peerChartDef(answerOf('capital expenditures'))).toThrow('peerChartDef: no metric names "capital_expenditures"')
  })

  // A pair whose subject or second company holds no value has peer_count 2 and one bar: the retired panel drew it. A
  // subject with no figure beside companies with one would draw a chart without the company the page is about, and a
  // concept FEATURED cannot name would break the card's label.
  it.each(Object.keys(NOT_SHOWING))('%s: shows nothing, and never mounts the card', async (name) => {
    // The default metric's answer decides, whatever it ranks on.
    const { container } = renderPanel({ revenue: answerOf(name) })
    await settle()
    expect(container).toBeEmptyDOMElement()
    expect(card.renders, 'the card never mounts').toBe(0)
  })

  it('mounts the card for a pair, in the same harness', async () => {
    renderPanel({ revenue: answerOf('pair') })
    await panelCard()
    expect(card.renders).toBeGreaterThan(0)
  })

  it('counts the rank over the companies with a value, never peer_count: a pair plus a withheld peer reads "#2 of 2"', async () => {
    const answer = answerOf('pair plus withheld')
    expect(answer.peer_count).toBe(3)
    const section = await openOn('pair plus withheld')
    await plotOf(section, 'Diluted EPS')
    expect(within(section).getByText(/ranks #/).closest('p')).toHaveTextContent('PPWB ranks #2 of 2 on diluted EPS')
    expect(section).not.toHaveTextContent(/of 3/)
  })

  // The chart's eleven slots: it never leaves out a company a slot could hold, and where a cohort is larger than its slots
  // the footnote says what the chart shows, so the bars never contradict the rank line's count unexplained.
  it('draws every company its eleven slots hold: the spread’s eleven, TNYX, the eleventh, among them, and says nothing of a cut', async () => {
    const answer = answerOf('spread')
    expect(answer.peers.filter((entry) => entry.value != null), 'eleven companies with a value').toHaveLength(11)
    renderPanel({ revenue: answer })
    const section = await panelCard()
    const { svg, bars } = await plotOf(section, 'Revenue')
    expect(bars.map((bar) => bar.getAttribute('data-period'))).toEqual(answer.peers.map((entry) => entry.ticker))
    expect([...svg.querySelectorAll('text[data-text="x"]')].map((tick) => tick.textContent)).toContain('TNYX')
    expect(within(section).getByText(/ranks #/).closest('p')).toHaveTextContent('SUBX ranks #6 of 11 on revenue')
    expect(footnote(section)).not.toHaveTextContent('The chart shows')
  })

  it.each(SHOWING.filter((name) => FIXTURE.cases[name].response.peers.filter((entry) => entry.value != null).length <= 11))(
    '%s: a cohort of eleven or fewer draws every company ranked, and its footnote says nothing of a cut',
    async (name) => {
      const answer = answerOf(name)
      const section = await openOn(name)
      const { bars } = await plotOf(section, peerChartDef(answer).title)
      expect(bars, 'a bar a company ranked').toHaveLength(answer.peers.filter((entry) => entry.value != null).length)
      expect(footnote(section)).not.toHaveTextContent('The chart shows')
    },
  )

  // A cohort larger than the eleven slots: the top eleven where the subject ranks among them, else the top ten and the
  // subject, either side of the slots' edge (the eleventh drawn among the top, the twelfth after the top ten); the top
  // never parts a tie, so it is the companies ranked that high, and where one rank fills the slots the footnote gives
  // the count alone.
  it.each([
    { name: 'cap', top: 'ABCDEFGHIJ', after: 'CAPM', ranks: 'CAPM ranks #13 of 14 on revenue', cut: 'The chart shows the top 10 of the 14 companies ranked, and CAPM.' },
    { name: 'cap, subject fifth', top: 'ABCDEFGHIJK', after: null, ranks: 'CAPE ranks #5 of 14 on revenue', cut: 'The chart shows the top 11 of the 14 companies ranked.' },
    { name: 'cap, subject eleventh', top: 'ABCDEFGHIJK', after: null, ranks: 'CAPK ranks #11 of 14 on revenue', cut: 'The chart shows the top 11 of the 14 companies ranked.' },
    { name: 'cap, subject twelfth', top: 'ABCDEFGHIJ', after: 'CAPL', ranks: 'CAPL ranks #12 of 14 on revenue', cut: 'The chart shows the top 10 of the 14 companies ranked, and CAPL.' },
    { name: 'cap, tie at the tenth', top: 'ABCDEFGHI', after: 'CAPM', ranks: 'CAPM ranks #13 of 14 on revenue', cut: 'The chart shows the top 9 of the 14 companies ranked, and CAPM.' },
    { name: 'cap, tie at the eleventh', top: 'ABCDEFGHIJ', after: null, ranks: 'CAPB ranks #2 of 12 on revenue', cut: 'The chart shows the top 10 of the 12 companies ranked.' },
    { name: 'cap, all tied', top: 'ABCDEFGHIJ', after: 'CAPL', ranks: 'CAPL ranks #1 of 12 on revenue', cut: 'The chart shows 11 of the 12 companies ranked.' },
  ])('$name: draws what its footnote says, "$cut"', async ({ name, top, after, ranks, cut }) => {
    const answer = answerOf(name)
    renderPanel({ revenue: answer })
    const section = await panelCard()
    const { svg, bars } = await plotOf(section, 'Revenue')
    const companies = [...top].map((letter) => `CAP${letter}`).concat(after ? [after] : [])
    expect(bars.map((bar) => bar.getAttribute('data-period')), 'a bar a company drawn').toEqual(companies)
    expect([...svg.querySelectorAll('text[data-text="x"]')].map((tick) => tick.textContent)).toEqual(companies)
    expect([rankLine(section).tagName, rankLine(section).textContent]).toEqual(['P', ranks])
    expect(footnote(section).textContent!.endsWith(`Fiscal years can differ by company. ${cut}`), footnote(section).textContent!).toBe(true)
    // The words never contradict the ranks: "the top N" is every company ranked N or better, and only those.
    const named = /the top (\d+) of/.exec(cut)
    if (named) {
      const atMost = Number(named[1])
      const ranked = answer.peers.filter((entry) => entry.rank != null && entry.rank <= atMost).map((entry) => entry.ticker)
      expect(companies.filter((ticker) => ticker !== after), `the top: every company ranked ${atMost} or better, and nothing ranked below`).toEqual(ranked)
    }
  })

  it('starts the values stop at the subject, which it names as this company, with its rank and its own fiscal year', async () => {
    renderPanel({ revenue: answerOf('spread') })
    const section = await panelCard()
    await plotOf(section, 'Revenue')
    const stop = within(section).getByRole('slider', { name: 'Revenue chart values' })
    expect(stop).toHaveAttribute('aria-valuenow', '5')
    expect(stop).toHaveAttribute('aria-valuetext', 'Synthetic Subject Corp, SUBX, this company, rank 6 of 11, FY2025, year ended December 31, 2025. Revenue: $113.2 billion.')
    fireEvent.keyDown(stop, { key: 'ArrowLeft' })
    expect(stop).toHaveAttribute('aria-valuetext', 'Synthetic Holdings Ltd, HLDX, rank 5 of 11, FY2025, year ended December 31, 2025. Revenue: $150.4 billion.')
  })

  // The tooltip names the company (chief design's merge condition on #1868): no tick, label or footnote prints a name, and
  // two companies can answer one ticker; and a subject drawn after the top ten carries its rank, as its values stop does.
  /** The tooltip's header for the values stop's company `i`, reached from the first by the keyboard. */
  const tipHeader = (section: HTMLElement, i: number) => {
    const stop = within(section).getByRole('slider', { name: 'Revenue chart values' })
    fireEvent.keyDown(stop, { key: 'Home' })
    for (let step = 0; step < i; step++) fireEvent.keyDown(stop, { key: 'ArrowRight' })
    return section.querySelector('[data-chart-tooltip] p')?.textContent
  }

  it('heads a tooltip with the ticker, the name, the rank and the year: the two companies that answer DUPX differ by name', async () => {
    renderPanel({ revenue: answerOf('duplicate ticker') })
    const section = await panelCard()
    await plotOf(section, 'Revenue')
    expect([tipHeader(section, 0), tipHeader(section, 1)]).toEqual([
      'DUPX · Synthetic Duplicate One Inc · #1 of 4 · FY2025 · year ended Dec 31, 2025',
      'DUPX · Synthetic Duplicate Two Corp · #2 of 4 · FY2025 · year ended Dec 31, 2025',
    ])
  })

  it('gives the rank in the tooltip of a subject drawn after the top ten, where the bars’ order cannot', async () => {
    renderPanel({ revenue: answerOf('cap') })
    const section = await panelCard()
    await plotOf(section, 'Revenue')
    expect(tipHeader(section, 10)).toBe('CAPM · Synthetic Capped M Inc · #13 of 14 · FY2025 · year ended Dec 31, 2025')
  })

  it('prints a CNY cohort in the engine’s CNY form, its axis, every value and its readout, and names the currency in its footnote', async () => {
    renderPanel({ revenue: answerOf('CNY revenue') })
    const cny = await panelCard()
    const { svg } = await plotOf(cny, 'Revenue')
    const printed = (role: string) => [...svg.querySelectorAll(`text[data-text="${role}"]`)].map((text) => text.textContent)
    expect([printed('tick'), printed('label')]).toEqual([CNY_TICKS, CNY_LABELS])
    expect(svg.textContent, 'no dollar sign anywhere on the plot').not.toContain('$')
    const stop = within(cny).getByRole('slider', { name: 'Revenue chart values' })
    expect(stop.getAttribute('aria-valuetext')).toMatch(CNY_READOUT)
    expect(footnote(cny)).toHaveTextContent(/^Companies with the same SEC industry code, each with its most recent annual revenue from SEC filings \(XBRL\), reported in CNY\. Fiscal years can differ by company\.$/)
  })

  it('says in its footnote that a drawn margin needs a source check, and lists it in Sources & checks', async () => {
    renderPanel({ revenue: answerOf('spread'), net_margin: answerOf('net margin') })
    const section = await panelCard()
    expect(footnote(section)).not.toHaveTextContent('source check')
    fireEvent.change(picker(section), { target: { value: 'net_margin' } })
    await plotOf(section, 'Net margin')
    expect(footnote(section)).toHaveTextContent(/each with its most recent annual net margin from SEC filings \(XBRL\)\. Fiscal years can differ by company\. Some figures here need a source check\. Sources & checks lists them\.$/)
    expect(within(section).getByText(/^MRGC, 2025: Calculated before 10 October 2026/)).toBeInTheDocument()
  })

  it('offers the nine metrics FEATURED names, at one width', async () => {
    renderPanel({ revenue: answerOf('spread') })
    const section = await panelCard()
    const select = picker(section)
    expect([...select.options].map((option) => [option.value, option.textContent])).toEqual([
      ['revenue', 'Revenue'], ['net_income', 'Net income'], ['gross_profit', 'Gross profit'], ['operating_income', 'Operating income'],
      ['net_margin', 'Net margin'], ['operating_margin', 'Operating margin'], ['gross_margin', 'Gross margin'], ['eps_diluted', 'Diluted EPS'],
      ['total_assets', 'Total assets'],
    ])
    expect(select.className.split(/\s+/)).toContain('w-56')
  })

  it('holds the plot’s room and the rank line’s while a metric picked loads, and says in the plot’s place why it draws no chart or that its read failed', async () => {
    let answer!: (value: PeerComparisonResponse) => void
    renderPanel({
      revenue: answerOf('spread'),
      eps_diluted: new Promise<PeerComparisonResponse>((resolve) => { answer = resolve }),
    })
    const section = await panelCard()
    await plotOf(section, 'Revenue')
    expect([rankLine(section).tagName, rankLine(section).textContent]).toEqual(['P', 'SUBX ranks #6 of 11 on revenue'])
    fireEvent.change(picker(section), { target: { value: 'eps_diluted' } })
    expect(within(section).getByRole('status', { name: 'Loading sector peers' })).toBeInTheDocument()
    expect(within(section).queryByRole('img')).toBeNull()
    // The rank line's room: the default answer's line laid out invisible in the line's type, a bone over it.
    const held = () => {
      const room = rankLine(section)
      expect(room).toHaveAttribute('data-held-rank')
      expect(room).toHaveAttribute('aria-hidden', 'true')
      expect([...room.children].map((child) => [child.tagName, child.className.includes('invisible'), child.textContent])[0]).toEqual(['P', true, 'SUBX ranks #6 of 11 on revenue'])
      return room.querySelectorAll(':scope > div').length
    }
    expect(held(), 'a bone over the held line while it loads').toBe(1)

    await act(async () => answer(answerOf('withheld peer')))
    expect((await inPlace(section)).textContent).toBe('Too few sector peers have diluted EPS figures to compare.')
    expect(held(), 'the room held, with no rank to give').toBe(0)

    fireEvent.change(picker(section), { target: { value: 'operating_income' } })
    expect(await within(section).findByText('Couldn’t load sector peers for operating income. Try another metric.')).toBeInTheDocument()
    expect(held(), 'the room held after a failed read').toBe(0)
    // The card stays, and the default metric draws again from its answer.
    fireEvent.change(picker(section), { target: { value: 'revenue' } })
    await plotOf(section, 'Revenue')
    expect([rankLine(section).tagName, rankLine(section).textContent]).toEqual(['P', 'SUBX ranks #6 of 11 on revenue'])
    expect(section.querySelector('[data-held-rank]')).toBeNull()
  })

  // Each reason a metric picked draws no chart, in plain words: the company's own figure missing or withheld; no other
  // company with a figure; a metric the panel cannot name.
  it.each([
    ['withheld subject, with peers', 'WSPX’s diluted EPS is unavailable, so it can’t be ranked.'],
    ['no gross profit, with peers', 'NGPX’s gross profit is unavailable, so it can’t be ranked.'],
    ['withheld peer', 'Too few sector peers have diluted EPS figures to compare.'],
  ])('%s, picked: says in the plot’s place "%s"', async (name, line) => {
    const section = await openOn(name)
    const place = await inPlace(section)
    expect(place.textContent).toBe(line)
    expect(within(section).queryByRole('img')).toBeNull()
    expect(rankLine(section)).toHaveAttribute('data-held-rank')
    if (NOT_SHOWING[name as keyof typeof NOT_SHOWING] === 'subject') expect(place.querySelector('.font-data'), 'the ticker in the data face').toHaveTextContent(answerOf(name).subject.ticker)
    // Sources & checks lists every company whose value is withheld, with no chart as with one.
    const withheld = answerOf(name).peers.filter((entry) => entry.provenance?.validation === 'unavailable')
    expect(withheld.map((entry) => within(section).getByText(new RegExp(`^${entry.ticker}, 2025: unavailable\\.`)).textContent)).toHaveLength(withheld.length)
  })

  it('says in the plot’s place that an answer ranked on a metric it cannot name cannot be shown', async () => {
    renderPanel({ revenue: answerOf('spread'), total_assets: answerOf('capital expenditures') })
    const section = await panelCard()
    fireEvent.change(picker(section), { target: { value: 'total_assets' } })
    expect((await inPlace(section)).textContent).toBe('Sector peers for total assets can’t be shown here.')
  })
})
