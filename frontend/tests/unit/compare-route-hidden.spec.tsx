import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports).
const h = vi.hoisted(() => ({
  enableCompare: false,
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

vi.mock('next/navigation', () => ({ notFound: h.notFound }))
vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_COMPARE() {
    return h.enableCompare
  },
}))

import CompareLayout from '@/app/compare/layout'

describe('Compare route gating (NEXT_PUBLIC_ENABLE_COMPARE)', () => {
  beforeEach(() => {
    h.notFound.mockClear()
  })

  it('404s /compare and /compare/result when the flag is off', () => {
    h.enableCompare = false
    expect(() => CompareLayout({ children: 'gated' })).toThrow('NEXT_NOT_FOUND')
    expect(h.notFound).toHaveBeenCalledTimes(1)
  })

  it('renders the routes when the flag is on', () => {
    h.enableCompare = true
    const out = CompareLayout({ children: 'visible' })
    expect(h.notFound).not.toHaveBeenCalled()
    expect(out).toBeTruthy()
  })
})
