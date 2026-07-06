import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import SectionImpression from '@/features/marketing/components/SectionImpression'

const mockAnalytics = vi.hoisted(() => ({
  homepageSectionViewed: vi.fn(),
}))
vi.mock('@/lib/analytics', () => ({ default: mockAnalytics, analytics: mockAnalytics }))

type ObserverCallback = (entries: Array<{ isIntersecting: boolean }>) => void

class MockIntersectionObserver {
  static instances: MockIntersectionObserver[] = []
  callback: ObserverCallback
  disconnect = vi.fn()
  observe = vi.fn()
  unobserve = vi.fn()

  constructor(callback: ObserverCallback) {
    this.callback = callback
    MockIntersectionObserver.instances.push(this)
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  MockIntersectionObserver.instances = []
  mockAnalytics.homepageSectionViewed.mockClear()
})

describe('SectionImpression', () => {
  it('renders children and no-ops (no throw, no event) without IntersectionObserver', () => {
    // jsdom has no IntersectionObserver by default — the homepage e2e asserts zero page
    // errors, so this must never throw.
    expect(typeof IntersectionObserver).toBe('undefined')

    render(
      <SectionImpression section="notable_filings">
        <p>content</p>
      </SectionImpression>
    )
    expect(screen.getByText('content')).toBeInTheDocument()
    expect(mockAnalytics.homepageSectionViewed).not.toHaveBeenCalled()
  })

  it('fires homepage_section_viewed exactly once, then disconnects', () => {
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

    render(
      <SectionImpression section="notable_filings">
        <p>content</p>
      </SectionImpression>
    )

    const observer = MockIntersectionObserver.instances[0]
    expect(observer).toBeDefined()
    expect(observer.observe).toHaveBeenCalledTimes(1)

    observer.callback([{ isIntersecting: false }])
    expect(mockAnalytics.homepageSectionViewed).not.toHaveBeenCalled()

    observer.callback([{ isIntersecting: true }])
    observer.callback([{ isIntersecting: true }])
    expect(mockAnalytics.homepageSectionViewed).toHaveBeenCalledTimes(1)
    expect(mockAnalytics.homepageSectionViewed).toHaveBeenCalledWith('notable_filings')
    expect(observer.disconnect).toHaveBeenCalled()
  })
})
