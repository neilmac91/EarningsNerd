import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'
import AskFilingDemo from '@/features/marketing/components/AskFilingDemo'
import ChangeReportDemo from '@/features/marketing/components/ChangeReportDemo'
import ProDepth from '@/features/marketing/components/ProDepth'
import RevenueBars from '@/features/marketing/components/RevenueBars'
import {
  AAPL_FY25_EDGAR_URL,
  SAMPLE_ANALYSIS_DATASET,
  SAMPLE_ASK,
  SAMPLE_CHANGE_REPORT,
} from '@/features/marketing/lib/landing-samples'
import { FREE_COPILOT_QUESTIONS } from '@/lib/planLimits'

/**
 * "What Pro adds" (the landing's fourth ruled row, D-045): the three product screens are the REAL product components
 * (CitationChip, KpiStrip, MetricsTable, WhatChanged) fed the static landing samples. These specs
 * prove the samples satisfy each component's contract at runtime, pin the accessibility shape the
 * design asks for, and keep the plan-cap copy on the lib/planLimits mirror.
 */

const flags = vi.hoisted(() => ({ analysis: false }))
vi.mock('@/lib/featureFlags', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/featureFlags')>()
  return {
    ...actual,
    get ENABLE_ANALYSIS() {
      return flags.analysis
    },
  }
})

const REVENUE_POINTS = [
  { period: 'FY2019', value: 260_174_000_000 },
  { period: 'FY2020', value: 274_515_000_000 },
  { period: 'FY2021', value: 365_817_000_000 },
  { period: 'FY2022', value: 394_328_000_000 },
]

describe('RevenueBars', () => {
  it('labels the chart for assistive tech and leaves a full tick above the tallest bar', () => {
    const { container } = render(<RevenueBars points={REVENUE_POINTS} />)
    const chart = screen.getByRole('img', {
      name: 'Revenue by fiscal year, FY2019 to FY2022: $260B, $275B, $366B, $394B',
    })
    expect(chart).toBeInTheDocument()

    // max $394.3B -> ceil(3.943) + 1 = 5 ticks of $100B; the axis tops out at 500.
    const ticks = ['0', '100', '200', '300', '400', '500']
    for (const tick of ticks) expect(within(chart).getByText(tick)).toBeInTheDocument()
    expect(within(chart).queryByText('600')).toBeNull()

    const bars = container.querySelectorAll('.bg-chart-1')
    expect(bars).toHaveLength(4)
    const tallest = bars[3] as HTMLElement
    expect(parseFloat(tallest.style.height)).toBeCloseTo((394.328 / 500) * 100, 1)
  })
})

describe('AskFilingDemo', () => {
  it('injects the real CitationChip for [1], [2] and [3], each reachable as an EDGAR anchor', () => {
    render(<AskFilingDemo />)
    expect(screen.getByText(SAMPLE_ASK.question)).toBeInTheDocument()

    const [total, growth, passage] = [1, 2, 3].map((n) => screen.getByRole('link', { name: new RegExp(`^Citation ${n}:`) }))
    for (const chip of [total, growth, passage]) {
      expect(chip).toHaveAttribute('href', AAPL_FY25_EDGAR_URL)
      expect(chip).toHaveAttribute('target', '_blank')
    }
    // Numbered as a live answer is: the server renumbers every marker, so an XBRL figure reads [1], never [F1].
    expect(total).toHaveAttribute('data-citation-kind', 'xbrl')
    expect(total).toHaveTextContent('[1]')
    expect(growth).toHaveAttribute('data-citation-kind', 'xbrl')
    expect(growth).toHaveTextContent('[2]')
    expect(passage).toHaveAttribute('data-citation-kind', 'text')
    expect(passage).toHaveTextContent('[3]')

    // The chips replaced the markers inside the answer: the answer paragraph holds all three anchors.
    const answer = screen.getByText(/Total net sales were/).closest('p')
    expect(answer).not.toBeNull()
    expect(within(answer as HTMLElement).getAllByRole('link')).toHaveLength(3)
    expect(answer!.textContent).not.toMatch(/\[F\d+\]/)
  })

  it('names each chip kind in plain words with its locator and what was checked', () => {
    render(<AskFilingDemo />)
    // The kind is the server's (fact or calculated), never the section label: the computed growth is not a filed figure.
    expect(screen.getByText('Filed figure')).toBeInTheDocument()
    expect(screen.getByText('Calculated figure')).toBeInTheDocument()
    expect(screen.getAllByText('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax')).toHaveLength(2)
    expect(screen.getByText('Passage')).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_ASK.citations[2].section_ref as string)).toBeInTheDocument()
    // The product's vocabulary (citationVerificationLabel), never a bare "Verified".
    expect(screen.getByText('Matches filing')).toBeInTheDocument()
    expect(screen.getByText('Calculated from filing')).toBeInTheDocument()
    expect(screen.getByText('Quote found in filing')).toBeInTheDocument()
    expect(screen.queryByText('Verified')).toBeNull()
  })

  it('keeps the static composer decorative: no button, hidden from assistive tech', () => {
    render(<AskFilingDemo />)
    expect(screen.queryByRole('button', { name: 'Ask' })).toBeNull()
    expect(screen.getByText('Ask this filing…').closest('[aria-hidden="true"]')).not.toBeNull()
  })
})

describe('AnalysisDemo', () => {
  it('renders the real KPI strip, the DOM revenue chart and the real metrics table from the sample', () => {
    render(<AnalysisDemo />)
    const first = SAMPLE_ANALYSIS_DATASET.periods[0].key
    const last = SAMPLE_ANALYSIS_DATASET.periods[SAMPLE_ANALYSIS_DATASET.periods.length - 1].key
    expect(screen.getByText(`Apple Inc. · Annual · ${first}–${last}`)).toBeInTheDocument()

    // The definitions name each metric; its actual reporting period accompanies the value.
    for (const label of ['Revenue', 'Net income', 'Net margin']) {
      const card = screen.getAllByRole('term').find((term) => term.textContent === label)!.parentElement!
      expect(within(card).getByText(last)).toBeInTheDocument()
      expect(within(card).getByRole('button', { name: new RegExp(`^${label}, ${last}:`) })).toBeInTheDocument()
    }

    expect(screen.getByRole('img', { name: new RegExp(`^Revenue by fiscal year, ${first} to ${last}:`) })).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: 'Metrics by period' })).toBeInTheDocument()
    const table = screen.getByRole('table')
    for (const period of SAMPLE_ANALYSIS_DATASET.periods) {
      expect(within(table).getByRole('columnheader', { name: period.key })).toBeInTheDocument()
    }
  })
})

describe('ChangeReportDemo', () => {
  it('renders the real WhatChanged report flattened into the frame, with no fake loading state', () => {
    const { container } = render(<ChangeReportDemo />)
    expect(screen.getByRole('heading', { name: 'What changed' })).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_CHANGE_REPORT.comparison_basis as string)).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_CHANGE_REPORT.metrics!.headline as string)).toBeInTheDocument()
    // The table (sm+) and the stacked rows (below sm) both carry every served change.
    for (const layout of ['table', 'rows']) {
      const scope = within(container.querySelector<HTMLElement>(`[data-change-layout="${layout}"]`)!)
      for (const item of SAMPLE_CHANGE_REPORT.metrics!.items) {
        expect(scope.getByText(item.display as string)).toBeInTheDocument()
      }
    }
    // The chrome-neutralising wrapper targets `[&>section]`: WhatChanged's section must stay its
    // direct child, or the frame grows a second border.
    const frame = container.querySelector('[data-capture="change-report"]')
    expect(frame).not.toBeNull()
    expect(frame!.querySelector(':scope > div > section')).not.toBeNull()
    // The sample carries no risk lines, so nothing on the sales surface pretends to load.
    expect(screen.queryAllByRole('status')).toHaveLength(0)
    expect(screen.queryByText('New risk factors')).toBeNull()
  })
})

describe('ProDepth', () => {
  beforeEach(() => {
    flags.analysis = false
  })

  it('is a labelled section with the Pro rows, the extras list and mirror-driven caps', () => {
    render(<ProDepth />)
    const section = screen.getByRole('region', { name: 'More ways to read one filing.' })
    expect(section.id).toBe('pro')
    expect(within(section).getByText('Ask it a question, then see what changed since the last one.')).toBeInTheDocument()

    for (const title of ['Ask this Filing', 'Change Report']) {
      expect(within(section).getByRole('heading', { level: 3, name: title })).toBeInTheDocument()
    }
    // One Pro chip, Ask this Filing's: both plans read the same Change Report (changeReportPlanClaims.spec.tsx).
    expect(within(section).getAllByText('Pro')).toHaveLength(1)

    expect(
      within(section).getByText(`Free accounts get ${FREE_COPILOT_QUESTIONS} questions.`, { exact: false }),
    ).toBeInTheDocument()

    expect(within(section).getByRole('heading', { level: 3, name: 'Also in Pro' })).toBeInTheDocument()
    expect(within(section).getByText('Watchlists are unlimited on both plans.')).toBeInTheDocument()
    // The extras, exactly: no history tile while no retention is enforced (D-046; summaryPlanClaims.spec.ts).
    const extras = within(section).getByRole('heading', { level: 4, name: 'Summary export' }).closest('ul')!
    expect(within(extras).getAllByRole('heading', { level: 4 }).map((h) => h.textContent)).toEqual(['Summary export', 'Filing alerts'])
    for (const tag of ['PDF', 'CSV', '10-K', '10-Q', '8-K']) {
      expect(within(section).getByText(tag)).toBeInTheDocument()
    }
  })

  // The flag invariant (nothing of Multi-Period or Excel while the route is off, both named while it is on) has
  // one gate, analysis-route-hidden.spec.tsx; this case pins the shape the flag-on row ships with, which that
  // gate does not read: the lead, the row's heading and Pro chip, the Excel tile and the CTA's href.
  it('with the analysis route on, renders the Multi-Period row, its CTA, the Excel tile and the lead as designed', () => {
    flags.analysis = true
    render(<ProDepth />)
    const section = screen.getByRole('region', { name: 'More ways to read one filing.' })
    expect(
      within(section).getByText('Ask it a question, read its periods side by side, see what changed since the last one.'),
    ).toBeInTheDocument()
    expect(within(section).getByRole('heading', { level: 3, name: 'Multi-Period Analysis' })).toBeInTheDocument()
    expect(within(section).getAllByText('Pro')).toHaveLength(2)
    expect(within(section).getByRole('heading', { level: 4, name: 'Excel export' })).toBeInTheDocument()
    expect(within(section).getByText('XLSX')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Try it on Apple/ })).toHaveAttribute('href', '/analysis?ticker=AAPL')
  })
})
