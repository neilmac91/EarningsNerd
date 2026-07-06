import { describe, expect, it } from 'vitest'
import { formatGrowth } from '@/features/analysis/lib/growth'
import { toneForConcept } from '@/features/analysis/lib/tonePolicy'

describe('formatGrowth', () => {
  it('renders a relative-growth series as a signed percentage (×100)', () => {
    expect(formatGrowth(0.183, false)).toEqual({ text: '+18.3%', direction: 'up' })
    expect(formatGrowth(-0.221, false)).toEqual({ text: '-22.1%', direction: 'down' })
  })

  it('renders a percent-unit series delta as percentage points, NOT ×100', () => {
    // 47.3% -> 38.3% is a -9.0pp move, not -900.0pp (the value is already point-scaled).
    expect(formatGrowth(-9.0, true)).toEqual({ text: '-9.0pp', direction: 'down' })
    expect(formatGrowth(4.97, true)).toEqual({ text: '+5.0pp', direction: 'up' })
  })

  it('renders the NOT_MEANINGFUL sentinel as "n/m" in flat tone', () => {
    expect(formatGrowth('nm', false)).toEqual({ text: 'n/m', direction: 'flat' })
    expect(formatGrowth('nm', true)).toEqual({ text: 'n/m', direction: 'flat' })
  })

  it('renders nothing for null/undefined (no prior period)', () => {
    expect(formatGrowth(null, false)).toEqual({ text: '', direction: 'flat' })
    expect(formatGrowth(undefined, false)).toEqual({ text: '', direction: 'flat' })
  })

  it('treats an exact-zero delta as flat, not up or down', () => {
    expect(formatGrowth(0, false).direction).toBe('flat')
    expect(formatGrowth(0, true).direction).toBe('flat')
  })
})

describe('toneForConcept', () => {
  it('inverts tone for debt/liabilities — an increase reads as loss, a decrease as gain', () => {
    expect(toneForConcept('long_term_debt', 'up')).toBe('down')
    expect(toneForConcept('long_term_debt', 'down')).toBe('up')
    expect(toneForConcept('current_liabilities', 'up')).toBe('down')
  })

  it('flattens tone for capex/investing/financing — direction implies no fixed valence', () => {
    expect(toneForConcept('capital_expenditures', 'up')).toBe('flat')
    expect(toneForConcept('investing_cash_flow', 'down')).toBe('flat')
    expect(toneForConcept('financing_cash_flow', 'up')).toBe('flat')
  })

  it('passes through the sign-based direction for every other concept', () => {
    expect(toneForConcept('revenue', 'up')).toBe('up')
    expect(toneForConcept('net_income', 'down')).toBe('down')
  })

  it('never overrides an already-flat direction', () => {
    expect(toneForConcept('long_term_debt', 'flat')).toBe('flat')
    expect(toneForConcept('capital_expenditures', 'flat')).toBe('flat')
  })
})
