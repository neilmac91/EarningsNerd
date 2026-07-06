import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// recharts measures the DOM, which jsdom can't do — stub it (same pattern as analysis-teaser.spec.tsx).
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ComposedChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}))

import TrendCharts from '@/features/analysis/components/TrendCharts'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

const dataset: AnalysisDataset = {
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
      concept: 'revenue',
      label: 'Revenue',
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: 'FY2023', value: 100, marker: 'F1' },
        { period: 'FY2024', value: 120, marker: 'F2', yoy: 0.2 },
      ],
    },
    {
      concept: 'gross_margin',
      label: 'Gross margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      points: [
        { period: 'FY2023', value: 70.0, marker: 'F3' },
        { period: 'FY2024', value: 68.0, marker: 'F4', yoy: -2.0 },
      ],
    },
    {
      concept: 'operating_margin',
      label: 'Operating margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      points: [
        { period: 'FY2023', value: 40.0, marker: 'F5' },
        { period: 'FY2024', value: 42.0, marker: 'F6', yoy: 2.0 },
      ],
    },
  ],
  inflections: [],
}

describe('TrendCharts legends', () => {
  it('shows a legend naming each line for a multi-series panel (Margins)', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.getByText('Margins')).toBeInTheDocument()
    expect(screen.getByText('Gross')).toBeInTheDocument()
    expect(screen.getByText('Operating')).toBeInTheDocument()
  })

  it('shows the growth-line legend entry for the top-line bar panel', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.getByText('Revenue')).toBeInTheDocument()
    expect(screen.getByText('YoY growth')).toBeInTheDocument()
  })
})
