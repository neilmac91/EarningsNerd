import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'

import KpiStrip from '@/features/analysis/components/KpiStrip'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

const annualDataset: AnalysisDataset = {
  ticker: 'TST',
  company_name: 'Test Co',
  mode: 'annual',
  period_key: 'FY2016..FY2025',
  periods: [
    { key: 'FY2016', fiscal_year: 2016, fiscal_period: 'FY', period_end: '2016-06-30' },
    { key: 'FY2025', fiscal_year: 2025, fiscal_period: 'FY', period_end: '2025-06-30' },
  ],
  series: [
    {
      concept: 'revenue',
      label: 'Revenue',
      unit: 'USD',
      percent: false,
      cagr: 0.134,
      points: [
        { period: 'FY2016', value: 91_200_000_000, marker: 'F1' },
        { period: 'FY2025', value: 281_700_000_000, marker: 'F2' },
      ],
    },
    {
      concept: 'net_income',
      label: 'Net income',
      unit: 'USD',
      percent: false,
      cagr: 0.195,
      points: [
        { period: 'FY2016', value: 20_500_000_000, marker: 'F3' },
        { period: 'FY2025', value: 101_800_000_000, marker: 'F4' },
      ],
    },
    {
      concept: 'free_cash_flow',
      label: 'Free cash flow',
      unit: 'USD',
      percent: false,
      cagr: 0.124,
      points: [
        { period: 'FY2016', value: 25_000_000_000, marker: 'F5' },
        { period: 'FY2025', value: 71_600_000_000, marker: 'F6' },
      ],
    },
    {
      // Percent-unit series: CAGR is always null (unit == "pure"), so the annual card falls
      // back to window_pp — this is the F1 fix (the card previously had no sub-metric at all).
      concept: 'net_margin',
      label: 'Net margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      window_pp: 13.6,
      window_pp_range: 'FY2016..FY2025',
      points: [
        { period: 'FY2016', value: 22.5, marker: 'F7' },
        { period: 'FY2025', value: 36.1, marker: 'F8' },
      ],
    },
  ],
  inflections: [],
}

describe('KpiStrip', () => {
  it('labels growth based on unverified history without labelling the verified current figure', () => {
    const flagged = structuredClone(annualDataset)
    flagged.series[0].points[0].reconciled = false
    flagged.series[0].points[1].reconciled = true
    flagged.series[0].cagr_reconciled = false
    flagged.series[3].window_pp_reconciled = false
    const { rerender } = render(<KpiStrip dataset={flagged} />)
    expect(screen.getAllByRole('button', { name: /comparison carries data note a/ })).toHaveLength(2)
    expect(screen.queryByText('Source check needed')).not.toBeInTheDocument()
    flagged.mode = 'quarterly'
    flagged.series[0].points[1].yoy = 0.2
    flagged.series[0].points[1].yoy_reconciled = false
    rerender(<KpiStrip dataset={flagged} />)
    expect(screen.getAllByRole('button', { name: /comparison carries data note a/ })).toHaveLength(1)
  })

  it('retains reconciliation on the latest populated KPI point', () => {
    const flagged = structuredClone(annualDataset)
    flagged.series[0].points[1].reconciled = false
    flagged.series[0].points.push({ period: 'FY2026', value: null, reconciled: true })
    flagged.series[1].points[1].reconciled = true
    const { rerender } = render(<KpiStrip dataset={flagged} />)
    const revenue = screen.getByRole('button', { name: /Revenue, FY2025:.*data note a/ })
    expect(revenue.querySelector('[data-note-kind="review"]')).toHaveTextContent('a')
    const card = revenue.closest('[data-analysis-kpi]') as HTMLElement
    expect(within(card).getByRole('term')).toHaveTextContent(/^Revenue$/)
    expect(within(card).getByText('FY2025')).toBeInTheDocument()
    rerender(<KpiStrip dataset={annualDataset} />)
    expect(screen.getByRole('button', { name: /Revenue, FY2025:/ }).querySelector('[data-note-kind="review"]')).not.toBeInTheDocument()
  })

  it('shows CAGR for monetary KPI cards in annual mode', () => {
    render(<KpiStrip dataset={annualDataset} />)
    expect(screen.getByText(/CAGR \+13\.4%/)).toBeInTheDocument()
    expect(screen.getByText(/CAGR \+19\.5%/)).toBeInTheDocument()
  })

  it('shows the window pp change (not a blank card) for the percent-unit net-margin KPI', () => {
    render(<KpiStrip dataset={annualDataset} />)
    // Previously blank (CAGR is null for percent series) — now shows the window's pp move.
    expect(screen.getByText(/Chg \+13\.6pp/)).toBeInTheDocument()
  })

  it('uses YoY (not CAGR) as the growth label in quarterly mode', () => {
    // Distinct yoy per concept so each KPI card's text is uniquely findable.
    const yoyByConcept: Record<string, number> = {
      revenue: 0.183,
      net_income: 0.231,
      free_cash_flow: -0.221,
      net_margin: 4.0, // percent series: already a pp delta
    }
    const quarterly: AnalysisDataset = {
      ...annualDataset,
      mode: 'quarterly',
      series: annualDataset.series.map((s) => ({
        ...s,
        points: s.points.map((p, i) => (i === 1 ? { ...p, yoy: yoyByConcept[s.concept] } : p)),
      })),
    }
    render(<KpiStrip dataset={quarterly} />)
    expect(screen.getByText(/YoY \+18\.3%/)).toBeInTheDocument()
    // The percent-unit card's quarterly YoY is a pp delta too.
    expect(screen.getByText(/YoY \+4\.0pp/)).toBeInTheDocument()
  })

  it('names the actual period of an older available metric and retains zero in the selected latest period', () => {
    const quarterly: AnalysisDataset = {
      ...structuredClone(annualDataset), mode: 'quarterly', period_key: '2026Q1..2026Q2',
      periods: [
        { key: '2026Q1', fiscal_year: 2026, fiscal_period: 'Q1', period_end: '2026-03-31' },
        { key: '2026Q2', fiscal_year: 2026, fiscal_period: 'Q2', period_end: '2026-06-30' },
      ],
    }
    quarterly.series.forEach((series) => {
      series.points[0].period = '2026Q1'
      series.points[1].period = '2026Q2'
    })
    quarterly.series[0].points[1].value = 0
    quarterly.series[0].points.push({ period: '2026Q3', value: 900 })
    quarterly.series[2].points[0].yoy = 0.2
    quarterly.series[2].points[1].value = null
    render(<KpiStrip dataset={quarterly} />)
    const cash = screen.getAllByRole('term').find((term) => term.textContent === 'Free cash flow')!.parentElement!
    expect(within(cash).getByText('Q1 2026', { exact: false })).toHaveTextContent('Q1 2026 · latest available')
    expect(within(cash).getByText(/YoY \+20\.0%/)).toBeInTheDocument()
    expect(within(cash).getByRole('button', { name: /Free cash flow, Q1 2026:/ })).toBeInTheDocument()
    const revenue = screen.getAllByRole('term').find((term) => term.textContent === 'Revenue')!.parentElement!
    expect(within(revenue).getByText('Q2 2026')).toBeInTheDocument()
    expect(within(revenue).queryByText(/latest available/)).not.toBeInTheDocument()
    expect(within(revenue).getByRole('button', { name: /Revenue, Q2 2026: \$0\.00,/ })).toBeInTheDocument()
    expect(screen.queryByText('Q3 2026')).not.toBeInTheDocument()
  })
})
