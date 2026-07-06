import { describe, expect, it } from 'vitest'
import { formatGrowth, windowGrowth } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import type { GrowthValue } from '@/features/analysis/api/analysis-api'

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

  it('degrades ANY unexpected string to "n/m" — never a garbage figure', () => {
    // The sentinel is a bare string over the wire (convention, not schema). If the backend ever
    // renamed it, the safe failure is an honest "n/m", not formatting the string as a number.
    expect(formatGrowth('n/m' as GrowthValue, false)).toEqual({ text: 'n/m', direction: 'flat' })
    expect(formatGrowth('not_meaningful' as GrowthValue, true)).toEqual({
      text: 'n/m',
      direction: 'flat',
    })
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

describe('windowGrowth', () => {
  it('resolves CAGR for monetary/per-share series', () => {
    expect(windowGrowth({ percent: false, cagr: 0.134, window_pp: null })).toEqual({
      value: 0.134,
      isPercent: false,
      label: 'CAGR',
    })
  })

  it('resolves the window pp change for percent-unit series (CAGR is always null there)', () => {
    expect(windowGrowth({ percent: true, cagr: null, window_pp: 13.6 })).toEqual({
      value: 13.6,
      isPercent: true,
      label: 'Chg',
    })
  })

  it('returns null (renders as —) when the window figure is genuinely absent', () => {
    expect(windowGrowth({ percent: false, cagr: null }).value).toBeNull()
    expect(windowGrowth({ percent: true, cagr: null, window_pp: null }).value).toBeNull()
  })
})

describe('applySeriesTone', () => {
  it('inverts tone when the dataset ships tone="inverted" (debt/liabilities)', () => {
    expect(applySeriesTone('inverted', 'up')).toBe('down')
    expect(applySeriesTone('inverted', 'down')).toBe('up')
  })

  it('flattens tone when the dataset ships tone="neutral" (capex/investing/financing)', () => {
    expect(applySeriesTone('neutral', 'up')).toBe('flat')
    expect(applySeriesTone('neutral', 'down')).toBe('flat')
  })

  it('passes through the sign-based direction for tone="normal"', () => {
    expect(applySeriesTone('normal', 'up')).toBe('up')
    expect(applySeriesTone('normal', 'down')).toBe('down')
  })

  it('defaults a missing tone (old fixture, deploy skew) to the sign-based reading', () => {
    expect(applySeriesTone(undefined, 'up')).toBe('up')
    expect(applySeriesTone(null, 'down')).toBe('down')
  })

  it('never overrides an already-flat direction', () => {
    expect(applySeriesTone('inverted', 'flat')).toBe('flat')
    expect(applySeriesTone('neutral', 'flat')).toBe('flat')
  })
})
