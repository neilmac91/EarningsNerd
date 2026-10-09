// A zone behind UTC, where a UTC-midnight report_date rendered through new Date() would show the day
// before (the filing-date-local-day.spec.tsx precedent; vitest isolates each file, so the pin is local).
process.env.TZ = 'America/New_York'

import { describe, expect, it } from 'vitest'
import { baseForm, isAmendment, periodKind, periodLabel, sortForms } from '@/features/filings/lib/filingPeriod'

const AT = '2026-07-26T00:00:00+00:00' // the wire shape: a UTC-midnight instant

describe('periodLabel: the filing index row name', () => {
  it.each([
    ['10-Q', 'Quarter ended Jul 26, 2026'],
    ['10-Q/A', 'Quarter ended Jul 26, 2026'],
    ['10-K', 'Fiscal year ended Jul 26, 2026'],
    ['10-K/A', 'Fiscal year ended Jul 26, 2026'],
    ['20-F', 'Fiscal year ended Jul 26, 2026'],
    ['40-F', 'Fiscal year ended Jul 26, 2026'],
    ['6-K', 'Period ended Jul 26, 2026'],
    ['8-K', 'Period ended Jul 26, 2026'],
  ])('%s → %s', (filing_type, label) => {
    expect(periodLabel({ filing_type, report_date: AT })).toBe(label)
  })

  it('keeps the calendar day of the period in a zone behind UTC', () => {
    expect(new Date(AT).getDate()).toBe(25) // control: the bug is observable here
    expect(periodLabel({ filing_type: '10-Q', report_date: AT })).toBe('Quarter ended Jul 26, 2026')
    expect(periodLabel({ filing_type: '10-Q', report_date: '2026-07-26' })).toBe('Quarter ended Jul 26, 2026')
  })

  it('is null without a usable period of report (the row says so instead of guessing)', () => {
    expect(periodLabel({ filing_type: '10-Q', report_date: undefined })).toBeNull()
    expect(periodLabel({ filing_type: '10-Q', report_date: '' })).toBeNull()
    expect(periodLabel({ filing_type: '10-Q', report_date: '2026-02-30' })).toBeNull()
  })
})

describe('form helpers', () => {
  it('strips the amendment suffix and classifies the base form', () => {
    expect(baseForm('10-K/A')).toBe('10-K')
    expect(isAmendment('10-K/A')).toBe(true)
    expect(isAmendment('10-K')).toBe(false)
    expect(periodKind('20-F/A')).toBe('annual')
    expect(periodKind('10-Q')).toBe('quarter')
    expect(periodKind('6-K')).toBe('period')
  })

  it('orders the form filter canonically, unknown forms last and alphabetical, without duplicates', () => {
    expect(sortForms(['10-Q', '8-K', '6-K', '10-K', '20-F', '10-K', '10-K/A'])).toEqual(['10-K', '10-Q', '20-F', '6-K', '10-K/A', '8-K'])
  })
})
