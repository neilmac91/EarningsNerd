import { describe, expect, it } from 'vitest'

import { datasetToCsv, exportFilename } from '@/features/analysis/lib/chartExport'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

// Quarterly payload: computed-Q4 columns exist, window figures never do (build_dataset computes
// cagr/window_pp in annual mode only).
const quarterly: AnalysisDataset = {
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
      label: 'Revenue, net', // comma — must be quoted in the CSV
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 310_000_000, marker: 'F1' },
        { period: '2024Q4', value: 330_000_000, marker: 'F2', derived: true },
      ],
    },
    {
      concept: 'net_margin',
      label: 'Net margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      points: [
        { period: '2024Q3', value: 38.3, marker: 'F3' },
        { period: '2024Q4', value: null },
      ],
    },
  ],
  inflections: [],
}

// Annual payload: window figures exist, computed-Q4 columns never do.
const annual: AnalysisDataset = {
  ...quarterly,
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
      cagr: 0.134,
      cagr_window: 'FY2023..FY2024',
      points: [
        { period: 'FY2023', value: 300_000_000, marker: 'F1' },
        { period: 'FY2024', value: 340_000_000, marker: 'F2' },
      ],
    },
    {
      concept: 'net_margin',
      label: 'Net margin',
      unit: 'pure',
      percent: true,
      cagr: null,
      window_pp: 2.7,
      window_pp_range: 'FY2023..FY2024',
      points: [
        { period: 'FY2023', value: 35.6, marker: 'F3' },
        { period: 'FY2024', value: 38.3, marker: 'F4' },
      ],
    },
  ],
  inflections: [],
}

describe('datasetToCsv — quarterly (computed Q4 columns)', () => {
  const lines = datasetToCsv(quarterly).trimEnd().split('\n')

  it('marks a column CONTAINING computed values in the header (instants there stay real)', () => {
    expect(lines[0]).toBe(
      'Metric,Concept,Unit,2024Q3,2024Q4 (contains computed Q4 values),Window growth,Window'
    )
  })

  it('emits raw machine-usable numbers, quotes commas, leaves window columns empty', () => {
    expect(lines[1]).toBe('"Revenue, net",revenue,USD,310000000,330000000,,')
  })

  it('marks percent-series units and leaves gaps empty', () => {
    expect(lines[2]).toBe('Net margin,net_margin,pure (×100 percent),38.3,,,')
  })
})

describe('datasetToCsv — annual (window figures)', () => {
  const lines = datasetToCsv(annual).trimEnd().split('\n')

  it('emits CAGR + its basis window for monetary series', () => {
    expect(lines[1]).toBe('Revenue,revenue,USD,300000000,340000000,0.134,FY2023..FY2024')
  })

  it('emits the pp window change for percent series', () => {
    expect(lines[2]).toBe(
      'Net margin,net_margin,pure (×100 percent),35.6,38.3,2.7 pp,FY2023..FY2024'
    )
  })
})

describe('exportFilename', () => {
  it('slugs the suffix and folds the period-range dots', () => {
    expect(exportFilename(quarterly, 'Top line & growth', 'png')).toBe(
      'TST_2024Q3-2024Q4_top-line-growth.png'
    )
  })
})