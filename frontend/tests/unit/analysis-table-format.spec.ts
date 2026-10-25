import { describe, expect, it } from 'vitest'
import type { AnalysisSeries } from '@/features/analysis/api/analysis-api'
import { formatTableGrowth, formatTableValue, tableComparisonText, tableCurrencyLabel, tableFigureText, tableTokenBudget } from '@/features/analysis/lib/tableFormat'
import type { FactProvenance } from '@/features/analysis/lib/provenance'

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
    expect(tableTokenBudget()).toBe(9)
    expect(tableTokenBudget(true, 'a')).toBe(7)
    expect(tableTokenBudget(false, 'ab')).toBe(7)
    expect(tableCurrencyLabel(series('CAD/shares'))).toBe('CAD per share')
    expect(tableCurrencyLabel(series('CAD'))).toBe('CAD')
    expect(tableCurrencyLabel(series('USD/shares'))).toBeNull()
    expect(formatTableValue(15154, series('CAD/shares'))).toBe('15.2K')
    expect(formatTableValue(-1e25, series('CAD'))).toBe('-1e25')
  })

  it('prints a figure cell at the budget its calculated mark and note letter leave, as MetricsTable does (M15)', () => {
    const usd = series('USD')
    const provenance = (method: FactProvenance['method']): FactProvenance => ({ version: 1, method, validation: 'passed', reasons: [], formula: null, inputs: [] })
    // Nine glyphs for a reported figure: "-$999.9M" fits; a calculated mark and a letter leave seven, so "-$1B".
    expect(tableFigureText(-999_900_000, {}, usd)).toBe('-$999.9M')
    expect(tableFigureText(-999_900_000, { provenance: provenance('calculated') }, usd, 'a')).toBe('-$1B')
    // With no provenance a derived figure is calculated; a figure's provenance outranks its derived flag.
    expect(tableFigureText(-999_900_000, { derived: true, provenance: null }, usd, 'a')).toBe('-$1B')
    expect(tableFigureText(-999_900_000, { derived: true, provenance: provenance('reported') }, usd, 'a')).toBe('-$999.9M')
    // The change line takes no calculated mark: only its own note letter narrows it.
    expect(tableComparisonText(1234.567, false)).toBe('+123,457%')
    expect(tableComparisonText(1234.567, false, 'a')).toBe('+123.5K%')
    expect(tableComparisonText(1234.567, false, 'ab')).toBe('+123K%')
  })
})
