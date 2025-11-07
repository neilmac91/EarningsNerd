import { fmtCurrency, fmtPercent } from '@/lib/format'

describe('numeric formatters', () => {
  it('formats currency values compactly by default', () => {
    expect(fmtCurrency(12500)).toBe('$12.5K')
  })

  it('formats currency with explicit digits and standard notation', () => {
    expect(fmtCurrency('42.5', { digits: 2, compact: false })).toBe('$42.50')
  })

  it('formats percentages with sign handling', () => {
    expect(fmtPercent('0.157', { digits: 2, signed: true })).toBe('+0.16%')
    expect(fmtPercent('-0.031', { digits: 1, signed: true })).toBe('-0.0%')
  })
})


