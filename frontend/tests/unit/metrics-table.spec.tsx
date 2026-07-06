import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import MetricsTable from '@/features/analysis/components/MetricsTable'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

const dataset: AnalysisDataset = {
  ticker: 'TST',
  company_name: 'Test Co',
  mode: 'quarterly',
  period_key: '2024Q3..2024Q4',
  periods: [
    { key: '2024Q3', fiscal_year: 2024, fiscal_period: 'Q3', period_end: '2024-09-30' },
    { key: '2024Q4', fiscal_year: 2024, fiscal_period: 'Q4', period_end: '2024-12-31' },
  ],
  series: [
    {
      concept: 'revenue',
      label: 'Revenue',
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 310_000_000, marker: 'F1', yoy: 0.05, qoq: 0.02 },
        { period: '2024Q4', value: 330_000_000, marker: 'F2', yoy: 0.08, qoq: 0.0645, derived: true },
      ],
    },
    {
      concept: 'eps_diluted',
      label: 'EPS (diluted)',
      unit: 'USD/shares',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 1.52, marker: 'F3' },
        { period: '2024Q4', value: null }, // EPS Q4 is never derived (share counts move)
      ],
    },
  ],
  inflections: [],
}

describe('MetricsTable', () => {
  it('renders values, deltas, the derived dagger, and — for missing points', () => {
    render(<MetricsTable dataset={dataset} />)

    expect(screen.getByText('Revenue')).toBeInTheDocument()
    expect(screen.getByText('EPS (diluted)')).toBeInTheDocument()
    // Derived Q4 revenue carries the computed dagger; the badge explains it.
    expect(screen.getByLabelText('Derived value')).toBeInTheDocument()
    expect(screen.getByText('† computed Q4')).toBeInTheDocument()
    // The never-derived EPS Q4 renders an em-dash placeholder.
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    // Quarterly mode shows QoQ deltas.
    expect(screen.getByText(/QoQ \+2\.0%/)).toBeInTheDocument()
  })

  it('hides the CAGR column entirely in quarterly mode (dead UI otherwise)', () => {
    render(<MetricsTable dataset={dataset} />)
    expect(screen.queryByText('CAGR')).not.toBeInTheDocument()
  })

  it('makes the Metric column sticky', () => {
    const { container } = render(<MetricsTable dataset={dataset} />)
    const firstBodyCell = container.querySelector('tbody tr td')
    expect(firstBodyCell).toHaveClass('sticky')
    expect(firstBodyCell).toHaveClass('left-0')
  })
})

describe('MetricsTable — annual mode: CAGR column, pp deltas, tone policy', () => {
  const annualDataset: AnalysisDataset = {
    ticker: 'TST',
    company_name: 'Test Co',
    mode: 'annual',
    period_key: 'FY2023..FY2024',
    periods: [
      { key: 'FY2023', fiscal_year: 2023, fiscal_period: 'FY', period_end: '2023-12-31' },
      { key: 'FY2024', fiscal_year: 2024, fiscal_period: 'FY', period_end: '2024-12-31' },
    ],
    series: [
      {
        concept: 'net_margin',
        label: 'Net margin',
        unit: 'pure',
        percent: true,
        tone: 'normal',
        cagr: null,
        window_pp: -9.0,
        window_pp_range: 'FY2023..FY2024',
        points: [
          { period: 'FY2023', value: 47.3, marker: 'F1' },
          { period: 'FY2024', value: 38.3, marker: 'F2', yoy: -9.0 },
        ],
      },
      {
        concept: 'long_term_debt',
        label: 'Long-term debt',
        unit: 'USD',
        percent: false,
        tone: 'inverted',
        cagr: -0.05,
        points: [
          { period: 'FY2023', value: 42_000_000_000, marker: 'F3' },
          { period: 'FY2024', value: 31_400_000_000, marker: 'F4', yoy: -0.252 },
        ],
      },
      {
        concept: 'investing_cash_flow',
        label: 'Investing cash flow',
        unit: 'USD',
        percent: false,
        tone: 'neutral',
        cagr: null,
        points: [
          { period: 'FY2023', value: 503_000_000, marker: 'F5' },
          { period: 'FY2024', value: -71_925_000_000, marker: 'F6', yoy: 'nm' },
        ],
      },
    ],
    inflections: [],
  }

  it('shows the CAGR column and formats a margin series delta as pp, not relative %', () => {
    render(<MetricsTable dataset={annualDataset} />)
    expect(screen.getByText('CAGR')).toBeInTheDocument()
    // 47.3% -> 38.3% is -9.0pp — never "-19.0%" (the relative-change convention this fixes).
    expect(screen.getByText(/YoY -9\.0pp/)).toBeInTheDocument()
  })

  it('renders "n/m" for a sign-flip growth value instead of a nonsensical percentage', () => {
    render(<MetricsTable dataset={annualDataset} />)
    expect(screen.getByText(/YoY n\/m/)).toBeInTheDocument()
  })

  it('inverts tone for long-term debt: a decrease renders gain-toned, not loss-toned', () => {
    render(<MetricsTable dataset={annualDataset} />)
    const delta = screen.getByText(/YoY -25\.2%/)
    expect(delta.className).toMatch(/gain/)
  })

  it('shows the window pp change in the CAGR column for a percent-unit row (never a dead —)', () => {
    render(<MetricsTable dataset={annualDataset} />)
    // net_margin: cagr is always null (unit "pure"), so the column resolves window_pp instead —
    // the same rule the KPI strip uses (windowGrowth). The tooltip names the basis window.
    const cell = screen.getByText('-9.0pp')
    expect(cell).toHaveAttribute('title', expect.stringContaining('FY2023..FY2024'))
  })
})
