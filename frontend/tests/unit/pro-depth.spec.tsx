import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AnalysisDemo from '@/features/marketing/components/AnalysisDemo'
import AskFilingDemo from '@/features/marketing/components/AskFilingDemo'
import ChangeReportDemo from '@/features/marketing/components/ChangeReportDemo'
import ProDepth from '@/features/marketing/components/ProDepth'
import RevenueBars from '@/features/marketing/components/RevenueBars'
import {
  AAPL_FY22_EDGAR_URL,
  SAMPLE_ANALYSIS_DATASET,
  SAMPLE_ASK,
  SAMPLE_CHANGE_REPORT,
} from '@/features/marketing/lib/landing-samples'
import { FREE_COPILOT_QUESTIONS, FREE_HISTORY_RETENTION_DAYS } from '@/lib/planLimits'

/**
 * "What Pro adds" (landing section 6): the three product screens are the REAL product components
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
  it('injects the real CitationChip for [F1] and [1], each reachable as an EDGAR anchor', () => {
    render(<AskFilingDemo />)
    expect(screen.getByText(SAMPLE_ASK.question)).toBeInTheDocument()

    const fact = screen.getByRole('link', { name: /^Citation F1:/ })
    const passage = screen.getByRole('link', { name: /^Citation 1:/ })
    for (const chip of [fact, passage]) {
      expect(chip).toHaveAttribute('href', AAPL_FY22_EDGAR_URL)
      expect(chip).toHaveAttribute('target', '_blank')
    }
    expect(fact).toHaveAttribute('data-citation-kind', 'xbrl')
    expect(fact).toHaveTextContent('[F1]')
    expect(passage).toHaveAttribute('data-citation-kind', 'text')
    expect(passage).toHaveTextContent('[1]')

    // The chips replaced the markers inside the answer: the answer paragraph holds both anchors.
    const answer = screen.getByText(/Services net sales were/).closest('p')
    expect(answer).not.toBeNull()
    expect(within(answer as HTMLElement).getAllByRole('link')).toHaveLength(2)
  })

  it('names each chip kind in plain words with its locator and verification', () => {
    render(<AskFilingDemo />)
    expect(screen.getByText('XBRL figure')).toBeInTheDocument()
    expect(
      screen.getByText('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax · Services'),
    ).toBeInTheDocument()
    expect(screen.getByText('Passage')).toBeInTheDocument()
    expect(screen.getByText('Item 7 · Segment Operating Performance')).toBeInTheDocument()
    expect(screen.getAllByText('Verified')).toHaveLength(2)
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

    // KpiStrip labels the latest point of each sample series.
    expect(screen.getByText(`Revenue (${last})`)).toBeInTheDocument()
    expect(screen.getByText(`Net income (${last})`)).toBeInTheDocument()
    expect(screen.getByText(`Net margin (${last})`)).toBeInTheDocument()

    expect(screen.getByRole('img', { name: new RegExp(`^Revenue by fiscal year, ${first} to ${last}:`) })).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: 'Metrics by period' })).toBeInTheDocument()
    const table = screen.getByRole('table')
    for (const period of SAMPLE_ANALYSIS_DATASET.periods) {
      expect(within(table).getByRole('columnheader', { name: period.key })).toBeInTheDocument()
    }
  })
})

describe('ChangeReportDemo', () => {
  it('renders the real WhatChanged report flattened into the frame, with skeleton risk columns', () => {
    const { container } = render(<ChangeReportDemo />)
    expect(screen.getByRole('heading', { name: 'What changed' })).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_CHANGE_REPORT.comparison_basis as string)).toBeInTheDocument()
    expect(screen.getByText(SAMPLE_CHANGE_REPORT.metrics!.headline as string)).toBeInTheDocument()
    for (const item of SAMPLE_CHANGE_REPORT.metrics!.items) {
      expect(screen.getByText(item.display)).toBeInTheDocument()
    }

    // The chrome-neutralising wrapper targets `[&>section]`: WhatChanged's section must stay its
    // direct child, or the frame grows a second border.
    const frame = container.querySelector('[data-capture="change-report"]')
    expect(frame).not.toBeNull()
    expect(frame!.querySelector(':scope > div > section')).not.toBeNull()

    // Raw skeleton bones are aria-hidden; each column's wrapper carries role + label (DS §4).
    const groups = screen.getAllByRole('status', { name: 'Risk factor text loads from the live report' })
    expect(groups).toHaveLength(2)
    expect(screen.getByText('New risk factors')).toBeInTheDocument()
    expect(screen.getByText('No longer cited')).toBeInTheDocument()
  })
})

describe('ProDepth', () => {
  beforeEach(() => {
    flags.analysis = false
  })

  it('is a labelled section with the three Pro rows, the extras grid and mirror-driven caps', () => {
    render(<ProDepth />)
    const section = screen.getByRole('region', { name: 'What Pro adds' })
    expect(section.id).toBe('pro')
    expect(
      within(section).getByText('Three ways to go deeper than one filing, each grounded in the same SEC data.'),
    ).toBeInTheDocument()

    for (const title of ['Ask this Filing', 'Multi-Period Analysis', 'Change Report']) {
      expect(within(section).getByRole('heading', { level: 3, name: title })).toBeInTheDocument()
    }
    expect(within(section).getAllByText('Pro')).toHaveLength(3)

    expect(
      within(section).getByText(`Free accounts get ${FREE_COPILOT_QUESTIONS} questions.`, { exact: false }),
    ).toBeInTheDocument()
    expect(
      within(section).getByText(`Free keeps ${FREE_HISTORY_RETENTION_DAYS} days.`, { exact: false }),
    ).toBeInTheDocument()

    expect(within(section).getByRole('heading', { level: 3, name: 'Also in Pro' })).toBeInTheDocument()
    expect(within(section).getByText('Watchlists are unlimited on both plans.')).toBeInTheDocument()
    for (const extra of ['Excel export', 'Summary export', 'Filing alerts', 'Full history']) {
      expect(within(section).getByRole('heading', { level: 4, name: extra })).toBeInTheDocument()
    }
    for (const tag of ['XLSX', 'PDF', 'CSV', '10-K', '10-Q', '8-K', 'Unlimited']) {
      expect(within(section).getByText(tag)).toBeInTheDocument()
    }
  })

  it('shows the Multi-Period CTA only while the analysis route exists', () => {
    const { unmount } = render(<ProDepth />)
    expect(screen.queryByRole('link', { name: /Try it on Apple/ })).toBeNull()
    unmount()

    flags.analysis = true
    render(<ProDepth />)
    expect(screen.getByRole('link', { name: /Try it on Apple/ })).toHaveAttribute('href', '/analysis?ticker=AAPL')
  })
})
