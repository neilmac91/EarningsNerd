import { fmtCurrency, fmtPercent, fmtPercentPoints } from '@/lib/format'
import type { FactProvenance } from './provenance'

type Figure = { concept?: string; unit?: string | null }

export const exactNumber = (value: number): string => value.toLocaleString('en-US', { maximumSignificantDigits: 21 })

const isMargin = ({ concept }: Figure) => concept?.endsWith('_margin') === true

/** These are presentation units, never a change to a value or its stored validation. */
export function compactFigure(value: number | null, figure: Figure): string {
  if (value == null) return 'Unavailable'
  if (figure.unit === 'growth fraction') return fmtPercent(value * 100, { signed: true })
  if (figure.unit === 'percentage points') return fmtPercentPoints(value)
  if (isMargin(figure) || figure.unit === 'percent') return fmtPercent(value)
  if (figure.unit === 'pure' || figure.concept === 'current_ratio') return `${value.toFixed(2)}×`
  const currency = /^([A-Z]{3})(\/shares)?$/.exec(figure.unit ?? '')
  if (currency) return fmtCurrency(value, { currency: currency[1], compact: !currency[2] && Math.abs(value) >= 1000, digits: currency[2] ? 2 : undefined })
  return exactNumber(value)
}

export function exactFigure(value: number, figure: Figure): string {
  const amount = exactNumber(value)
  if (figure.unit === 'growth fraction') return `${amount} (growth fraction)`
  if (figure.unit === 'percentage points') return `${amount} percentage points`
  if (isMargin(figure) || figure.unit === 'percent') return `${amount}%`
  if (figure.unit === 'pure' || figure.concept === 'current_ratio') return `${amount} (ratio)`
  if (figure.unit?.endsWith('/shares')) return `${amount} ${figure.unit.slice(0, -7)} per share`
  return [amount, figure.unit].filter(Boolean).join(' ')
}

const FORMULAS: Record<string, string> = {
  'FY - YTD9': 'Full year − first nine months',
  'YTD9 - YTD6': 'First nine months − first six months',
  'YTD6 - Q1': 'First six months − first quarter',
  '100 * operating_income / revenue': 'Operating income ÷ revenue × 100',
  '100 * net_income / revenue': 'Net income ÷ revenue × 100',
  '100 * gross_profit / revenue': 'Gross profit ÷ revenue × 100',
  'operating_cash_flow - abs(capital_expenditures)': 'Operating cash flow − absolute cash capital expenditures',
  'current_assets - current_liabilities': 'Current assets − current liabilities',
  'current_assets / current_liabilities': 'Current assets ÷ current liabilities',
}

export const formulaWords = (formula: string) => FORMULAS[formula] ?? formula.replaceAll('_', ' ')

/** Substitute only formula shapes whose operand identities are known. Input list order differs
 * between ratios and quarter subtraction; guessing from a slash can reverse the arithmetic. */
export function substitutedFormula(provenance?: FactProvenance | null): string | null {
  if (!provenance?.formula || provenance.inputs.length !== 2 || provenance.inputs.some((input) => input.value == null)) return null
  const { formula, inputs } = provenance
  const amount = (value: number) => value < 0 ? `(${exactNumber(value)})` : exactNumber(value)
  if (['FY - YTD9', 'YTD9 - YTD6', 'YTD6 - Q1'].includes(formula)) {
    return `${amount(inputs[0].value!)} − ${amount(inputs[1].value!)}`
  }
  const margin = /^100 \* (\w+) \/ revenue$/.exec(formula)
  const difference = /^(\w+) - (?:abs\((\w+)\)|(\w+))$/.exec(formula)
  const ratio = /^(\w+) \/ (\w+)$/.exec(formula)
  if (!FORMULAS[formula]) return null
  const names = margin ? [margin[1], 'revenue'] : difference ? [difference[1], difference[2] ?? difference[3]] : ratio ? [ratio[1], ratio[2]] : null
  if (!names) return null
  const operands = names.map((name) => inputs.filter((input) => input.concept === name))
  if (operands.some((matches) => matches.length !== 1)) return null
  const [first, second] = operands.map(([input]) => input.value!)
  if (margin || ratio) return `${amount(first)} ÷ ${amount(second)}${margin ? ' × 100' : ''}`
  return `${amount(first)} − ${difference?.[2] ? `|${exactNumber(second)}|` : amount(second)}`
}
