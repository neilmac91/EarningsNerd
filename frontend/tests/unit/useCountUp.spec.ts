import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'

import { useCountUp } from '@/hooks/useCountUp'

function mockReducedMotion(reduce: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: reduce && q.includes('reduce'),
    media: q,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

// v2 contract (design-system cutover): the initial state IS the target, so server
// markup, no-JS, and reduced motion all show the final formatted value — the rAF
// tween only runs client-side when motion is allowed, re-interpolating 0 → value.
describe('useCountUp', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows the final formatted value when reduced motion is preferred (no tween)', () => {
    mockReducedMotion(true)
    const { result } = renderHook(() => useCountUp(42))
    expect(result.current).toBe('42')
  })

  it('renders the final value on first commit even when motion is allowed (SSR/hydration safety)', () => {
    mockReducedMotion(false)
    const { result } = renderHook(() => useCountUp(42))
    expect(result.current).toBe('42')
  })

  it('applies the format option', () => {
    mockReducedMotion(true)
    const { result } = renderHook(() => useCountUp(391, { format: (v) => `$${v.toFixed(1)}B` }))
    expect(result.current).toBe('$391.0B')
  })
})
