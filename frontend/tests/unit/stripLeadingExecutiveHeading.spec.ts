import { describe, it, expect } from 'vitest'
import { stripLeadingExecutiveHeading } from '@/lib/stripLeadingExecutiveHeading'

describe('stripLeadingExecutiveHeading (T1.7)', () => {
  it('removes a leading "## Executive Summary" heading', () => {
    const md = '## Executive Summary\n\nRevenue rose 85%.\n\n## Financials\n\n- Revenue: $81.6B'
    const out = stripLeadingExecutiveHeading(md)
    expect(out).not.toContain('## Executive Summary')
    expect(out).toContain('Revenue rose 85%.')
    // Later section headings are untouched.
    expect(out).toContain('## Financials')
  })

  it('skips blank leading lines before the heading', () => {
    const out = stripLeadingExecutiveHeading('\n\n## Executive Summary\n\nBody')
    expect(out).not.toContain('Executive Summary')
    expect(out).toContain('Body')
  })

  it('is a no-op when the first heading is not Executive Summary', () => {
    const md = '## Financials\n\n- Revenue: $1B\n\n## Executive Summary later'
    expect(stripLeadingExecutiveHeading(md)).toBe(md)
  })

  it('only strips the FIRST occurrence, not a later Executive Summary heading', () => {
    const md = 'Intro line\n## Executive Summary\nBody'
    // Not leading (a non-heading line precedes it) → untouched.
    expect(stripLeadingExecutiveHeading(md)).toBe(md)
  })

  it('handles empty input', () => {
    expect(stripLeadingExecutiveHeading('')).toBe('')
  })
})
