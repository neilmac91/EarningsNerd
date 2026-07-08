import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports).
const h = vi.hoisted(() => ({
  enableFullTextSearch: false,
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

vi.mock('next/navigation', () => ({ notFound: h.notFound }))
vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_FULLTEXT_SEARCH() {
    return h.enableFullTextSearch
  },
}))

import SearchLayout from '@/app/search/layout'

describe('Search route gating (NEXT_PUBLIC_ENABLE_FULLTEXT_SEARCH)', () => {
  beforeEach(() => {
    h.notFound.mockClear()
  })

  it('404s /search when the flag is off (hidden product)', () => {
    h.enableFullTextSearch = false
    expect(() => SearchLayout({ children: 'gated' })).toThrow('NEXT_NOT_FOUND')
    expect(h.notFound).toHaveBeenCalledTimes(1)
  })

  it('renders the route when the flag is on', () => {
    h.enableFullTextSearch = true
    const out = SearchLayout({ children: 'visible' })
    expect(h.notFound).not.toHaveBeenCalled()
    expect(out).toBeTruthy()
  })
})
