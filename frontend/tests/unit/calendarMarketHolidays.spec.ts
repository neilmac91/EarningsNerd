import { describe, expect, it } from 'vitest'
import { marketHolidayName } from '@/features/calendar/lib/dates'

// The calendar's month navigation has no bound, so the NYSE full closures are computed for any year.
describe('marketHolidayName', () => {
  it.each([
    '2019-04-19',
    '2024-03-29',
    '2025-04-18',
    '2026-04-03',
    '2027-03-26',
    '2028-04-14',
    '2029-03-30',
    '2030-04-19',
    '2035-03-23',
  ])('names Good Friday on %s', (iso) => {
    expect(marketHolidayName(iso)).toBe('Good Friday')
  })

  it('names no Good Friday on the Thursday before it or the Monday after', () => {
    expect(marketHolidayName('2029-03-29')).toBeNull()
    expect(marketHolidayName('2029-04-02')).toBeNull()
  })

  it('observes Juneteenth from 2022, when the NYSE first closed for it', () => {
    expect(marketHolidayName('2022-06-20')).toBe('Juneteenth')
    expect(marketHolidayName('2026-06-19')).toBe('Juneteenth')
    expect(marketHolidayName('2021-06-18')).toBeNull()
    expect(marketHolidayName('2020-06-19')).toBeNull()
  })
})
