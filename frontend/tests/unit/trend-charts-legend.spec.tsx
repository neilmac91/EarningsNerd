import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

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
    {
      concept: 'long_term_debt',
      label: 'Long-term debt',
      unit: 'USD',
      percent: false,
      tone: 'inverted',
      cagr: null,
      points: [
        { period: 'FY2023', value: 40, marker: 'F7' },
        { period: 'FY2024', value: 35, marker: 'F8' },
      ],
    },
    {
      concept: 'shareholders_equity',
      label: "Shareholders' equity",
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: 'FY2023', value: 900, marker: 'F9' },
        { period: 'FY2024', value: 1000, marker: 'F10' },
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

  it('marks the right-axis series in the balance-sheet legend (dual axis)', () => {
    render(<TrendCharts dataset={dataset} />)
    // Equity dwarfs debt — it moves to the right axis and the legend says so explicitly.
    expect(screen.getByText('Equity (right)')).toBeInTheDocument()
    expect(screen.getByText('Long-term debt')).toBeInTheDocument()
  })

  it('keeps a single axis (no "(right)" suffix) when only the right-axis series is present', () => {
    const equityOnly: AnalysisDataset = {
      ...dataset,
      series: dataset.series.filter((s) =>
        ['revenue', 'shareholders_equity'].includes(s.concept)
      ),
    }
    render(<TrendCharts dataset={equityOnly} />)
    expect(screen.queryByText('Equity (right)')).not.toBeInTheDocument()
  })
})

describe('TrendCharts panel controls', () => {
  it('expands a panel to full grid width and back', () => {
    render(<TrendCharts dataset={dataset} />)
    const expand = screen.getAllByRole('button', { name: 'Expand chart' })[0]
    expect(expand).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(expand)
    expect(screen.getAllByRole('button', { name: 'Collapse chart' })[0]).toHaveAttribute(
      'aria-expanded',
      'true'
    )
    // The expanded panel spans both grid columns and grows h-56 → h-96.
    const card = expand.closest('section')
    expect(card?.className).toMatch(/md:col-span-2/)
    expect(card?.querySelector('.h-96')).not.toBeNull()

    fireEvent.click(screen.getAllByRole('button', { name: 'Collapse chart' })[0])
    expect(card?.className).not.toMatch(/md:col-span-2/)
    expect(card?.querySelector('.h-56')).not.toBeNull()
  })

  it('renders no data-label control (removed after the AAPL field test — dense series collide)', () => {
    render(<TrendCharts dataset={dataset} />)
    expect(screen.queryByRole('button', { name: /data labels/i })).not.toBeInTheDocument()
  })

  it('shows the PNG download only when exportEnabled (Pro results surface)', () => {
    const { rerender } = render(<TrendCharts dataset={dataset} />)
    expect(screen.queryByRole('button', { name: 'Download chart as PNG' })).not.toBeInTheDocument()
    rerender(<TrendCharts dataset={dataset} exportEnabled />)
    expect(screen.getAllByRole('button', { name: 'Download chart as PNG' }).length).toBeGreaterThan(0)
  })
})