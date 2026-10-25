import { describe, expect, it } from 'vitest'
import type { AnalysisSeries } from '@/features/analysis/api/analysis-api'
import { formatTableGrowth, formatTableValue, tableCurrencyLabel, tableTokenBudget } from '@/features/analysis/lib/tableFormat'

const series = (unit: string, percent = false): AnalysisSeries => ({ concept: 'test', label: 'Test', unit, percent, points: [], cagr: null })

describe('fixed-column display formatting', () => {
  it('retains ordinary EPS cents, amounts and percentages when they fit', () => {
    expect(formatTableValue(5.33, series('USD/shares'))).toBe('$5.33')
    expect(formatTableValue(-21_500_000_000, series('USD'))).toBe('-$21.5B')
    expect(formatTableValue(30.9, series('percent', true))).toBe('30.9%')
    expect(formatTableValue(2.2256, series('pure'))).toBe('2.23×')
    expect(formatTableGrowth(-0.091, false)).toBe('-9.1%')
    expect(formatTableGrowth('nm', false)).toBe('n/m')
    expect(formatTableGrowth(null, false)).toBe('')
  })

  it.each([
    [15154, 'USD/shares', false, '$15.2K'],
    [-15154, 'USD/shares', false, '-$15.2K'],
    [-999.99, 'USD/shares', false, '-$1.0K'],
    [-999_900_000, 'USD', false, '-$1B'],
    [123456.78, 'pure', false, '123.5K×'],
    [-123456.78, 'pure', false, '-123K×'],
    [123456.78, 'percent', true, '123.5K%'],
    [-1e25, 'USD', false, '-$1e25'],
  ])('keeps %s %s atomic through bounded precision or notation', (value, unit, percent, expected) => {
    const output = formatTableValue(value, series(unit, percent))
    expect(output).toBe(expected)
    expect(output.length).toBeLessThanOrEqual(7)
  })

  it('keeps comparison basis units and signs for large percentages and percentage points', () => {
    expect(formatTableGrowth(1234.567, false)).toBe('+123.5K%')
    expect(formatTableGrowth(-123456.7, true)).toBe('-123Kpp')
    expect(formatTableGrowth(1e25, true)).toBe('+1e25pp')
    expect(formatTableGrowth(-1e23, false)).toBe('-1e25%')
  })

  it('reserves space for marks without changing source data or currency identity', () => {
    // A calculated figure carries no dagger, so only a note letter takes room from the nine glyphs.
    expect(tableTokenBudget()).toBe(9)
    expect(tableTokenBudget('a')).toBe(8)
    expect(tableTokenBudget('ab')).toBe(7)
    expect(tableCurrencyLabel(series('CAD/shares'))).toBe('CAD per share')
    expect(tableCurrencyLabel(series('CAD'))).toBe('CAD')
    expect(tableCurrencyLabel(series('USD/shares'))).toBeNull()
    expect(formatTableValue(15154, series('CAD/shares'))).toBe('15.2K')
    expect(formatTableValue(-1e25, series('CAD'))).toBe('-1e25')
  })
})
