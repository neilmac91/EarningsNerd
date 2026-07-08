import { describe, it, expect } from 'vitest'
import { fiscalYear, groupByFiscalYear } from '@/features/filings/lib/fiscalYear'

describe('fiscalYear', () => {
  it('buckets a 10-K by its period-of-report, not its filing date', () => {
    // FY2025 10-K filed 2026-02-13 must bucket under 2025, not 2026.
    expect(fiscalYear({ report_date: '2025-12-31', filing_date: '2026-02-13T00:00:00+00:00' })).toBe('2025')
  })

  it('falls back to filing_date when report_date is absent', () => {
    expect(fiscalYear({ filing_date: '2024-05-01' })).toBe('2024')
    expect(fiscalYear({ report_date: undefined, filing_date: '2024-05-01' })).toBe('2024')
  })

  it('returns empty string for a missing date (caller skips it)', () => {
    expect(fiscalYear({ filing_date: '' })).toBe('')
  })

  it('reads the year from the ISO prefix without a timezone shift', () => {
    // A UTC-midnight Jan-1 that new Date() would render as Dec-31 in a negative-offset zone.
    expect(fiscalYear({ report_date: '2023-01-01', filing_date: '2023-03-01' })).toBe('2023')
  })
})

describe('groupByFiscalYear', () => {
  it('groups by fiscal year and keeps within-year order', () => {
    const filings = [
      { report_date: '2025-12-31', filing_date: '2026-02-13' }, // FY2025 10-K
      { report_date: '2025-09-30', filing_date: '2025-11-01' }, // FY2025 Q3
      { report_date: '2024-12-31', filing_date: '2025-02-10' }, // FY2024 10-K
    ]
    const grouped = groupByFiscalYear(filings)
    expect(Object.keys(grouped).sort()).toEqual(['2024', '2025'])
    expect(grouped['2025']).toHaveLength(2)
    expect(grouped['2024']).toHaveLength(1)
    // The 10-K filed in 2026 is NOT bucketed under 2026.
    expect(grouped['2026']).toBeUndefined()
  })

  it('skips filings with no usable date', () => {
    expect(groupByFiscalYear([{ filing_date: '' }])).toEqual({})
  })
})
