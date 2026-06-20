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

describe('useCountUp', () => {
  afterEach(() => vi.restoreAllMocks())

  it('snaps straight to the final value when reduced motion is preferred (no tween)', () => {
    mockReducedMotion(true)
    const { result } = renderHook(() => useCountUp(42, 800))
    expect(result.current).toBe(42)
  })

  it('starts at 0 when motion is allowed (then animates up)', () => {
    mockReducedMotion(false)
    // First commit renders 0; the rAF tween advances it afterward (timing not asserted here).
    const { result } = renderHook(() => useCountUp(42, 800))
    expect(result.current).toBe(0)
  })
})
