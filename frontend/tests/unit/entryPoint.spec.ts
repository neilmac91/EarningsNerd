import { describe, it, expect, afterEach, vi } from 'vitest'

import { getEntryPoint } from '@/lib/entryPoint'

// jsdom exposes window.location and document.referrer; we override them per case.
function setLocation(search: string) {
  Object.defineProperty(window, 'location', {
    value: { search, origin: 'https://www.earningsnerd.io' },
    writable: true,
  })
}

function setReferrer(referrer: string) {
  Object.defineProperty(document, 'referrer', { value: referrer, configurable: true })
}

describe('getEntryPoint', () => {
  afterEach(() => vi.restoreAllMocks())

  it('prefers an explicit ?entry= param over the referrer', () => {
    setLocation('?entry=hero')
    setReferrer('https://www.earningsnerd.io/')
    expect(getEntryPoint()).toBe('hero')
  })

  it('truncates an overlong explicit entry to 64 chars', () => {
    setLocation('?entry=' + 'x'.repeat(200))
    setReferrer('')
    expect(getEntryPoint()).toHaveLength(64)
  })

  it('maps the homepage referrer to "homepage"', () => {
    setLocation('')
    setReferrer('https://www.earningsnerd.io/')
    expect(getEntryPoint()).toBe('homepage')
  })

  it('maps a company-page referrer to "company_page"', () => {
    setLocation('')
    setReferrer('https://www.earningsnerd.io/company/AAPL')
    expect(getEntryPoint()).toBe('company_page')
  })

  it('maps the exact /compare route to "compare"', () => {
    setLocation('')
    setReferrer('https://www.earningsnerd.io/compare')
    expect(getEntryPoint()).toBe('compare')
  })

  it('maps a /compare/ subpath to "compare"', () => {
    setLocation('')
    setReferrer('https://www.earningsnerd.io/compare/result')
    expect(getEntryPoint()).toBe('compare')
  })

  it('does not false-match a /compare-prefixed route to "compare"', () => {
    setLocation('')
    setReferrer('https://www.earningsnerd.io/compare-plans')
    expect(getEntryPoint()).toBe('internal')
  })

  it('reports "external" for an off-origin referrer', () => {
    setLocation('')
    setReferrer('https://www.google.com/')
    expect(getEntryPoint()).toBe('external')
  })

  it('reports "direct" when there is no referrer', () => {
    setLocation('')
    setReferrer('')
    expect(getEntryPoint()).toBe('direct')
  })
})
