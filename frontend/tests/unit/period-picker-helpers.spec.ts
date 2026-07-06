/** PeriodPicker range logic: chips, default window, and the single-anchor range mutation. */
import { describe, expect, it } from 'vitest'
import { chipsFor, defaultRange, nextRange } from '@/features/analysis/components/PeriodPicker'
import type { AnalysisCoverage } from '@/features/analysis/api/analysis-api'

const coverage: AnalysisCoverage = {
  ticker: 'TST',
  company_name: 'Test Co',
  supported: true,
  reason: null,
  syncing: false,
  synced_at: null,
  limits: { annual: 3, quarterly: 4 },
  annual: [
    { key: 'FY2019', fiscal_year: 2019, period_end: '2019-12-31', has_core: false },
    { key: 'FY2020', fiscal_year: 2020, period_end: '2020-12-31', has_core: true },
    { key: 'FY2021', fiscal_year: 2021, period_end: '2021-12-31', has_core: true },
    { key: 'FY2022', fiscal_year: 2022, period_end: '2022-12-31', has_core: true },
    { key: 'FY2023', fiscal_year: 2023, period_end: '2023-12-31', has_core: true },
  ],
  quarterly: [
    { key: '2023Q2', fiscal_year: 2023, fiscal_period: 'Q2', period_end: '2023-06-30', derived: false },
    { key: '2023Q4', fiscal_year: 2023, fiscal_period: 'Q4', period_end: '2023-12-31', derived: true },
  ],
}

describe('chipsFor', () => {
  it('disables annual years without core data and flags derived quarters', () => {
    const annual = chipsFor(coverage, 'annual')
    expect(annual.find((c) => c.key === 'FY2019')?.disabled).toBe(true)
    expect(annual.find((c) => c.key === 'FY2023')?.disabled).toBe(false)

    const quarterly = chipsFor(coverage, 'quarterly')
    expect(quarterly.find((c) => c.key === '2023Q4')?.derived).toBe(true)
    expect(quarterly.find((c) => c.key === '2023Q2')?.derived).toBe(false)
  })
})

describe('defaultRange', () => {
  it('selects the newest cap-sized window of enabled periods', () => {
    expect(defaultRange(coverage, 'annual')).toEqual({ start: 'FY2021', end: 'FY2023' })
  })

  it('returns null when nothing is selectable', () => {
    expect(defaultRange({ ...coverage, annual: [], quarterly: [] }, 'annual')).toBeNull()
  })
})

describe('nextRange', () => {
  const keys = ['FY2019', 'FY2020', 'FY2021', 'FY2022', 'FY2023']
  const range = { start: 'FY2021', end: 'FY2023' }

  it('extends toward an earlier click by moving the start', () => {
    expect(nextRange(keys, range, 'FY2020', 10)).toEqual({ start: 'FY2020', end: 'FY2023' })
  })

  it('clamps to the cap by pulling the far endpoint in', () => {
    expect(nextRange(keys, range, 'FY2019', 3)).toEqual({ start: 'FY2019', end: 'FY2021' })
  })

  it('moves the nearer endpoint for a click inside the range', () => {
    expect(nextRange(keys, { start: 'FY2019', end: 'FY2023' }, 'FY2022', 10)).toEqual({
      start: 'FY2019',
      end: 'FY2022',
    })
  })

  it('ignores unknown keys', () => {
    expect(nextRange(keys, range, 'FY1999', 10)).toEqual(range)
  })
})
