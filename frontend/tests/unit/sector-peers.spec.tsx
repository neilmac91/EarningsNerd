/* =============================================================================
   sector-peers.spec.tsx: the company page's Sector peers panel (E251; features/peers)
   -----------------------------------------------------------------------------
   The panel on the peers fixture (tests/unit/fixtures/peers-cohorts.json, which
   backend/tests/unit/test_peers_fixture_contract.py holds to the service), its read answered here, rendered as the page
   renders it: the gate (SectorPeers) reads the default metric and loads the card only for a cohort.
   - E251's gaps, each a gate: a bank's label is the answer's `concept` (asked for revenue, it answers net interest
     income, and the first option, the plot's name, the rank line, the footnote and the readout all say so); no chart of
     0 or 1 bars (an answer whose subject or second company holds no value renders nothing, and the card never mounts,
     whatever `peer_count` says); the rank's denominator is the companies with a value, never `peer_count`.
   - Its behaviour: every cohort the panel shows draws the subject in chart-1 and every other company in the context ink,
     in both themes; the chart draws every company its eleven slots hold (a cohort of eleven or fewer whole, the spread's
     eleventh among them), and fourteen draw the top ten and the subject, or the top eleven where the subject is among
     them, the footnote saying what the chart shows, and nothing where it shows every company; the values stop starts
     at the subject and says
     who it is; the footnote names a currency other than the dollar and a drawn value that needs a source check; the
     picker offers the nine metrics FEATURED names at one width; a metric picked holds the plot's room while it loads,
     and says in its place when too few companies report it or its read fails.
   The engine's drawing is its own gate's (trend-charts-v2.spec.tsx, over these cohorts through the panel's builder),
   the tooltip swatch among it; the mount, the key and the boundary are company-sector-peers-mount.spec.tsx's, and the
   page as CI ships it tests/e2e/company-sector-peers.spec.ts's.
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
import { drawn } from '@/features/peers/lib/cohort'
import { peerChartDef } from '@/features/peers/lib/peerChart'
import { peerBarCases, type PeerFixture } from './chartPlan'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/peers-cohorts.json', 'utf8')) as PeerFixture
const answerOf = (name: string): PeerComparisonResponse => structuredClone(FIXTURE.cases[name].response)
/** Every cohort the panel shows (chartPlan.ts peerBarCases, through the panel's own builder). */
const SHOWING = peerBarCases(FIXTURE).map(([name]) => name)

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

  // A pair whose subject or second company holds no value has peer_count 2 and one bar: the retired panel drew it.
  it.each(['production single', 'no facts', 'withheld peer', 'withheld subject'])('%s: shows nothing, and never mounts the card', async (name) => {
    const answer = answerOf(name)
    expect(answer.peers.filter((entry) => entry.value != null).length, 'one company or none with a value').toBeLessThan(2)
    // The default metric's answer decides, whatever it ranks on.
    const { container } = renderPanel({ revenue: answer })
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

  it('draws the top ten and then the subject where it ranks below them: fourteen companies draw eleven, the subject last, and the footnote says so', async () => {
    const answer = answerOf('cap')
    renderPanel({ revenue: answer })
    const section = await panelCard()
    const { svg, bars } = await plotOf(section, 'Revenue')
    expect(bars.map((bar) => bar.getAttribute('data-period'))).toEqual([...'ABCDEFGHIJ'].map((letter) => `CAP${letter}`).concat('CAPM'))
    expect([...svg.querySelectorAll('text[data-text="x"]')].map((tick) => tick.textContent)).toEqual([...'ABCDEFGHIJ'].map((letter) => `CAP${letter}`).concat('CAPM'))
    expect(within(section).getByText(/ranks #/).closest('p')).toHaveTextContent('CAPM ranks #13 of 14 on revenue')
    expect(footnote(section)).toHaveTextContent(/Fiscal years can differ by company\. The chart shows the top 10 of the 14 companies ranked, and CAPM\.$/)
  })

  it('draws the top eleven where the subject ranks among them, and the footnote says so', async () => {
    const answer = answerOf('cap, subject fifth')
    renderPanel({ revenue: answer })
    const section = await panelCard()
    const { bars } = await plotOf(section, 'Revenue')
    expect(bars.map((bar) => bar.getAttribute('data-period'))).toEqual([...'ABCDEFGHIJK'].map((letter) => `CAP${letter}`))
    expect(within(section).getByText(/ranks #/).closest('p')).toHaveTextContent('CAPE ranks #5 of 14 on revenue')
    expect(footnote(section)).toHaveTextContent(/Fiscal years can differ by company\. The chart shows the top 11 of the 14 companies ranked\.$/)
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

  it('names a currency other than the dollar in its footnote, and a drawn value that needs a source check', async () => {
    renderPanel({ revenue: answerOf('CNY revenue') })
    const cny = await panelCard()
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

  it('holds the plot’s room while a metric picked loads, and says in its place when too few companies report it or its read fails', async () => {
    let answer!: (value: PeerComparisonResponse) => void
    const sparse = { ...answerOf('production single'), concept: 'net_income' }
    renderPanel({
      revenue: answerOf('spread'),
      net_income: new Promise<PeerComparisonResponse>((resolve) => { answer = resolve }),
    })
    const section = await panelCard()
    fireEvent.change(picker(section), { target: { value: 'net_income' } })
    expect(within(section).getByRole('status', { name: 'Loading sector peers' })).toBeInTheDocument()
    expect(within(section).queryByRole('img')).toBeNull()
    await act(async () => answer(sparse))
    expect(await within(section).findByText('Too few sector peers report net income to compare.')).toBeInTheDocument()
    expect(within(section).queryByText(/ranks #/)).toBeNull()

    fireEvent.change(picker(section), { target: { value: 'operating_income' } })
    expect(await within(section).findByText('Couldn’t load sector peers for operating income. Try another metric.')).toBeInTheDocument()
    // The card stays, and the default metric draws again from its answer.
    fireEvent.change(picker(section), { target: { value: 'revenue' } })
    await plotOf(section, 'Revenue')
    expect(within(section).getByText(/ranks #/).closest('p')).toHaveTextContent('SUBX ranks #6 of 11 on revenue')
  })
})
