/** PeriodPicker range logic: visible options and independently edited, bounded endpoints. */
import { describe, expect, it } from 'vitest'
import { optionsFor, defaultRange, latestRange, nextRange } from '@/features/analysis/components/PeriodPicker'
import type { AnalysisCoverage } from '@/features/analysis/api/analysis-api'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'

describe('analysis period labels', () => {
  it('formats fiscal-quarter keys for full and compact display without recasting annual or unknown labels', () => {
    expect(formatAnalysisPeriod('2026Q2')).toBe('Q2 2026')
    expect(formatAnalysisPeriod('2026Q2', 'short')).toBe('Q2 ’26')
    expect(formatAnalysisPeriod('FY2026')).toBe('FY2026')
    expect(formatAnalysisPeriod('FY2026', 'short')).toBe('FY2026')
    expect(formatAnalysisPeriod('2026Q5')).toBe('2026Q5')
    expect(formatAnalysisPeriod('Trailing 12 months')).toBe('Trailing 12 months')
  })
})

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

describe('optionsFor', () => {
  it('disables annual years without core data and flags derived quarters', () => {
    const annual = optionsFor(coverage, 'annual')
    expect(annual.find((c) => c.key === 'FY2019')?.disabled).toBe(true)
    expect(annual.find((c) => c.key === 'FY2023')?.disabled).toBe(false)

    const quarterly = optionsFor(coverage, 'quarterly')
    expect(quarterly.find((c) => c.key === '2023Q4')).toMatchObject({ derived: true, label: 'Q4 2023' })
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
  const options = optionsFor(coverage, 'annual')
  const range = { start: 'FY2021', end: 'FY2023' }

  it('keeps the selected From and pulls To inside the cap', () => {
    expect(nextRange(options, range, 'start', 'FY2020', 3)).toEqual({ start: 'FY2020', end: 'FY2022' })
  })

  it('keeps the selected To and pulls From inside the cap', () => {
    expect(nextRange(options, { start: 'FY2020', end: 'FY2021' }, 'end', 'FY2023', 3)).toEqual(range)
  })

  it('moves the other endpoint when the reader crosses it', () => {
    expect(nextRange(options, range, 'end', 'FY2020', 3)).toEqual({ start: 'FY2020', end: 'FY2020' })
    expect(nextRange(options, { start: 'FY2020', end: 'FY2021' }, 'start', 'FY2023', 3)).toEqual({ start: 'FY2023', end: 'FY2023' })
  })

  it('ignores missing and disabled endpoints, and can start from no selection', () => {
    expect(nextRange(options, range, 'start', 'FY1999', 3)).toEqual(range)
    expect(nextRange(options, range, 'start', 'FY2019', 3)).toEqual(range)
    expect(nextRange(options, null, 'start', 'FY2020', 3)).toEqual({ start: 'FY2020', end: 'FY2020' })
  })

  it('counts unavailable years inside the cap and never clamps onto a disabled year', () => {
    const withGap = options.map((option) => ({ ...option, disabled: ['FY2019', 'FY2021'].includes(option.key) }))
    expect(latestRange(withGap, 3)).toEqual({ start: 'FY2022', end: 'FY2023' })
    expect(nextRange(withGap, range, 'start', 'FY2020', 2)).toEqual({ start: 'FY2020', end: 'FY2020' })
    expect(nextRange(withGap, { start: 'FY2020', end: 'FY2020' }, 'end', 'FY2023', 3)).toEqual({ start: 'FY2022', end: 'FY2023' })
  })
})
