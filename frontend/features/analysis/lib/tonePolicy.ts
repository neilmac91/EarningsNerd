import type { Direction } from '@/lib/financialTone'

// Metrics where an INCREASE is conventionally a cost/risk signal, not good news — invert so up
// reads as loss (red) and down reads as gain (green). Debt/liabilities growth is the textbook
// case the product's own deterministic signals already treat as a red flag (detect_debt_build).
const INVERTED_CONCEPTS = new Set<string>(['long_term_debt', 'current_liabilities'])

// Metrics with no fixed valence — a capex ramp, an investing swing, or a financing-activity
// change is a strategic choice (growth investment, buyback, refinancing), not inherently good or
// bad. Coloring these by sign alone would imply a judgment the data doesn't support, so they stay
// neutral regardless of direction.
const NEUTRAL_CONCEPTS = new Set<string>([
  'capital_expenditures',
  'investing_cash_flow',
  'financing_cash_flow',
])

/**
 * Map a sign-based direction to the tone actually displayed for a given metric concept.
 * Everything not listed keeps the default sign-based reading (up = gain, down = loss).
 */
export function toneForConcept(concept: string, direction: Direction): Direction {
  if (direction === 'flat') return 'flat'
  if (NEUTRAL_CONCEPTS.has(concept)) return 'flat'
  if (INVERTED_CONCEPTS.has(concept)) return direction === 'up' ? 'down' : 'up'
  return direction
}
