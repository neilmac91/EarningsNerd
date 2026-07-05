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
})
