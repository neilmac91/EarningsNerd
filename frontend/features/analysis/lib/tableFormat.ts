import type { AnalysisSeries, GrowthValue } from '@/features/analysis/api/analysis-api'
import { fmtCurrency, fmtPercent, fmtPercentPoints } from '@/lib/format'
import { formatGrowth } from './growth'

const currencyFromUnit = (unit: string): string => {
  const code = unit.split('/')[0].trim().toUpperCase()
  return /^[A-Z]{3}$/.test(code) ? code : 'USD'
}

/** Non-USD rows state currency once beside the metric, including the per-share basis. */
export function tableCurrencyLabel(series: AnalysisSeries): string | null {
  if (series.percent || series.unit === 'pure') return null
  const currency = currencyFromUnit(series.unit)
  return currency === 'USD' ? null : `${currency}${series.unit.endsWith('/shares') ? ' per share' : ''}`
}

// A fixed financial column has room for nine data glyphs, less its note letter: only a note that questions the number
// draws one (markedNote), and a calculated figure draws no dagger. Formatting is display-only: SourceValue keeps the
// original number and comparison.
export function tableTokenBudget(letter = ''): number {
  return Math.max(4, 9 - letter.length)
}

function bounded(candidates: string[], budget: number): string {
  return candidates.find((candidate) => [...candidate].length <= budget) ?? candidates.at(-1)!
}

function number(value: number, digits: number, notation: 'standard' | 'compact' | 'scientific' = 'standard', signed = false): string {
  return new Intl.NumberFormat('en-US', {
    notation, minimumFractionDigits: notation === 'standard' ? digits : 0,
    maximumFractionDigits: digits, signDisplay: signed ? 'exceptZero' : 'auto',
  }).format(value).replace('E+', 'e').replace('E', 'e')
}

/** Prefer the usual financial format, then lower precision, compact units, scientific notation. */
export function formatTableValue(value: number, series: AnalysisSeries, budget = 7): string {
  if (series.percent || series.unit === 'pure') {
    const suffix = series.percent ? '%' : '×'
    const digits = series.percent ? 1 : 2
    const ordinary = series.percent ? fmtPercent(value, { digits }) : `${number(value, digits)}${suffix}`
    return bounded([ordinary, `${number(value, 0)}${suffix}`, `${number(value, 1, 'compact')}${suffix}`, `${number(value, 0, 'compact')}${suffix}`, `${number(value, 0, 'scientific')}${suffix}`], budget)
  }
  const currency = currencyFromUnit(series.unit)
  const perShare = series.unit.endsWith('/shares')
  if (currency !== 'USD') {
    return bounded([
      number(value, perShare ? 2 : 1, perShare ? 'standard' : 'compact'),
      ...(perShare && Math.abs(value) < 1000 ? [number(value, 1)] : []),
      number(value, 1, 'compact'), number(value, 0, 'compact'), number(value, 0, 'scientific'),
    ], budget)
  }
  const ordinary = fmtCurrency(value, { currency, ...(perShare ? { digits: 2, compact: false } : { compact: true }) })
  const scientific = new Intl.NumberFormat('en-US', { style: 'currency', currency, notation: 'scientific', maximumFractionDigits: 0 }).format(value).replace('E+', 'e').replace('E', 'e')
  return bounded([
    ordinary,
    ...(perShare && Math.abs(value) < 1000 ? [fmtCurrency(value, { currency, digits: 1, compact: false })] : []),
    fmtCurrency(value, { currency, digits: 1, compact: true }),
    fmtCurrency(value, { currency, digits: 0, compact: true }),
    scientific,
  ], budget)
}

/** Values remain fractions for growth and percentage points for margin changes. */
export function formatTableGrowth(value: GrowthValue | null | undefined, isPercent: boolean, budget = 8): string {
  const ordinary = formatGrowth(value, isPercent).text
  if (typeof value !== 'number') return ordinary
  const amount = isPercent ? value : value * 100
  const suffix = isPercent ? 'pp' : '%'
  const zeroDigits = isPercent ? fmtPercentPoints(value, { digits: 0 }) : fmtPercent(amount, { digits: 0, signed: true })
  return bounded([ordinary, zeroDigits, `${number(amount, 1, 'compact', true)}${suffix}`, `${number(amount, 0, 'compact', true)}${suffix}`, `${number(amount, 0, 'scientific', true)}${suffix}`], budget)
}
