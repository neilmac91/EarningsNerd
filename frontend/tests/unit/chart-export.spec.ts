import { describe, expect, it } from 'vitest'

import { exportFilename } from '@/features/analysis/lib/chartExport'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'

// Tabular export left this module for the server-built Excel workbook (owner decision D1) —
// what remains client-side is the PNG path and its filename convention.
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
      label: 'Revenue, net',
      unit: 'USD',
      percent: false,
      cagr: null,
      points: [
        { period: '2024Q3', value: 310_000_000, marker: 'F1' },
        { period: '2024Q4', value: 330_000_000, marker: 'F2', derived: true },
      ],
    },
  ],
  inflections: [],
}

describe('exportFilename', () => {
  it('slugs the suffix and folds the period-range dots', () => {
    expect(exportFilename(quarterly, 'Top line & growth', 'png')).toBe(
      'TST_2024Q3-2024Q4_top-line-growth.png'
    )
  })

  it('names the Excel workbook exactly like the backend Content-Disposition', () => {
    // AnalysisPageClient downloads the xlsx under exportFilename(dataset, `${mode}-metrics`,
    // 'xlsx') — the same "{ticker}_{range}_{mode}-metrics.xlsx" the route header advertises,
    // so the two names can never disagree.
    expect(exportFilename(quarterly, `${quarterly.mode}-metrics`, 'xlsx')).toBe(
      'TST_2024Q3-2024Q4_quarterly-metrics.xlsx'
    )
  })
})
