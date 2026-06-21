import { describe, it, expect } from 'vitest'
import { findExcerptMatch, MIN_MATCH_LEN } from '@/features/filings/components/copilot/excerptMatch'

// The "spike": prove an excerpt can be located in rendered filing text despite markdown stripping
// (**bold**, # headings, | tables |) and whitespace differences — the core risk of the in-app viewer.

describe('findExcerptMatch', () => {
  it('finds an exact passage and returns offsets that slice it back out', () => {
    const haystack = 'Some intro. Revenue increased to $391.0B this year. More text.'
    const excerpt = 'Revenue increased to $391.0B this year.'
    const m = findExcerptMatch(haystack, excerpt)
    expect(m).not.toBeNull()
    // Offsets bound the alphanumeric span (leading/trailing punctuation like the final "." excluded).
    expect(haystack.slice(m!.start, m!.end)).toBe('Revenue increased to $391.0B this year')
  })

  it('matches across markdown emphasis the renderer would drop', () => {
    // Excerpt has no asterisks (as it appears on screen); the source markdown does.
    const haystack = 'MD&A. Revenue **increased** to $391.0B on strong demand.'
    const excerpt = 'Revenue increased to $391.0B on strong demand'
    const m = findExcerptMatch(haystack, excerpt)
    expect(m).not.toBeNull()
    // Offsets span from "Revenue" through the last matched alphanumeric ("demand").
    expect(haystack.slice(m!.start, m!.end)).toContain('Revenue **increased** to $391.0B on strong demand')
  })

  it('matches despite collapsed/normalized whitespace and newlines', () => {
    const haystack = 'Item 1A — Risk Factors\n\nSupply   chain\ndisruptions could materially affect results.'
    const excerpt = 'Supply chain disruptions could materially affect results.'
    const m = findExcerptMatch(haystack, excerpt)
    expect(m).not.toBeNull()
    expect(haystack.slice(m!.start, m!.end)).toContain('Supply')
    expect(haystack.slice(m!.start, m!.end)).toContain('results')
  })

  it('matches a quoted span inside a labelled excerpt', () => {
    const haystack = 'The company stated that operating margin expanded to 30.1 percent.'
    const excerpt = 'Item 7 — MD&A: "operating margin expanded to 30.1 percent"'
    const m = findExcerptMatch(haystack, excerpt)
    expect(m).not.toBeNull()
    expect(haystack.slice(m!.start, m!.end)).toContain('operating margin expanded to 30.1 percent')
  })

  it('anchors via a leading-prefix fallback when the model added a trailing clause', () => {
    const haystack = 'We expect gross margin to remain stable in the coming year.'
    const excerpt = 'We expect gross margin to remain stable in the coming year, per management commentary.'
    const m = findExcerptMatch(haystack, excerpt)
    expect(m).not.toBeNull()
    expect(haystack.slice(m!.start, m!.end)).toContain('gross margin to remain stable')
  })

  it('returns null for a fabricated excerpt not in the text', () => {
    const haystack = 'Revenue increased to $391.0B this year.'
    const excerpt = 'The company announced a special dividend of $5 per share.'
    expect(findExcerptMatch(haystack, excerpt)).toBeNull()
  })

  it('returns null for an excerpt below the minimum match length', () => {
    expect('tiny'.length).toBeLessThan(MIN_MATCH_LEN)
    expect(findExcerptMatch('Revenue increased to $391.0B this year.', 'tiny')).toBeNull()
  })

  it('handles empty inputs', () => {
    expect(findExcerptMatch('', 'anything at all here')).toBeNull()
    expect(findExcerptMatch('some haystack text', '')).toBeNull()
  })
})
