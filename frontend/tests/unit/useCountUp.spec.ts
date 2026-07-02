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

  it('arms the tween from 0 in a pre-paint layout effect when motion is allowed', () => {
    mockReducedMotion(false)
    const { result } = renderHook(() => useCountUp(42))
    // The INITIAL state is the final value (that is what SSR markup carries), but the
    // mount-time layout effect resets to the tween start before the browser paints —
    // no value→0→value flash. Post-mount the hook reports the start of the count-up.
    expect(result.current).toBe('0')
  })

  it('applies the format option', () => {
    mockReducedMotion(true)
    const { result } = renderHook(() => useCountUp(391, { format: (v) => `$${v.toFixed(1)}B` }))
    expect(result.current).toBe('$391.0B')
  })
})
