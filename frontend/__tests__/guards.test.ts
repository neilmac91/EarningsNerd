import { describe, expect, it } from 'vitest'
import { fmtEPS, fmtPct, fmtUSD, nonEmpty, showSection } from '@/lib/guards'

describe('guards', () => {
  it('identifies non-empty markdown', () => {
    expect(nonEmpty('## Heading')).toBe(true)
    expect(nonEmpty('   ')).toBe(false)
    expect(showSection('')).toBeNull()
  })

  it('formats USD with premium formatting', () => {
    expect(fmtUSD(1200000000)).toBe('$1.2B')
    expect(fmtUSD(1250)).toBe('$1,250.0')
  })

  it('formats percentages and EPS', () => {
    expect(fmtPct(0.123)).toBe('12.3%')
    expect(fmtEPS(1.678)).toBe('1.68')
  })
})
