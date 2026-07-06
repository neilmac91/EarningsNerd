import { describe, expect, it } from 'vitest'

import { datasetToCsv, exportFilename } from '@/features/analysis/lib/chartExport'
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
      label: 'Revenue, net', // comma — must be quoted in the CSV
      unit: 'USD',
      percent: false,
      cagr: 0.134,
      cagr_window: 'FY2016..FY2025',
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
      window_pp: 2.7,
      window_pp_range: 'FY2019..FY2024',
      points: [
        { period: '2024Q3', value: 38.3, marker: 'F3' },
        { period: '2024Q4', value: null },
      ],
    },
  ],
  inflections: [],
}

describe('datasetToCsv', () => {
  const lines = datasetToCsv(dataset).trimEnd().split('\n')

  it('emits a header with period columns, marking fully-computed Q4 columns in the header', () => {
    expect(lines[0]).toBe(
      'Metric,Concept,Unit,2024Q3,2024Q4 (computed Q4),Window growth,Window'
    )
  })

  it('emits raw machine-usable numbers and quotes fields containing commas', () => {
    expect(lines[1]).toBe(
      '"Revenue, net",revenue,USD,310000000,330000000,0.134,FY2016..FY2025'
    )
  })

  it('marks percent-series units, leaves gaps empty, and suffixes pp on the window figure', () => {
    expect(lines[2]).toBe(
      'Net margin,net_margin,pure (×100 percent),38.3,,2.7 pp,FY2019..FY2024'
    )
  })
})

describe('exportFilename', () => {
  it('slugs the suffix and folds the period-range dots', () => {
    expect(exportFilename(dataset, 'Top line & growth', 'png')).toBe(
      'TST_2024Q3-2024Q4_top-line-growth.png'
    )
  })
})