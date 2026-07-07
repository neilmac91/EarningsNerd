import { describe, expect, it } from 'vitest'
import {
  recommendedFilingNoun,
  selectRecommendedFiling,
} from '@/features/filings/lib/recommendedFiling'
import type { Filing } from '@/features/filings/api/filings-api'

// Minimal Filing factory — only the fields the recommendation logic reads matter here.
const filing = (id: number, filing_type: string, filing_date: string): Filing => ({
  id,
  filing_type,
  filing_date,
  accession_number: `acc-${id}`,
  document_url: `https://sec.gov/doc/${id}`,
  sec_url: `https://sec.gov/archive/${id}`,
})

describe('selectRecommendedFiling', () => {
  it('picks the single most recent filing regardless of type', () => {
    // The reported bug: a newer 10-Q must beat the older 10-K, so the banner never claims a stale
    // annual report is "most recent" while quarterly reports have shipped since.
    const filings = [
      filing(1, '10-K', '2025-07-30'),
      filing(2, '10-Q', '2025-10-29'),
      filing(3, '10-Q', '2026-01-28'),
      filing(4, '10-Q', '2026-04-29'),
    ]
    expect(selectRecommendedFiling(filings)?.id).toBe(4)
    expect(selectRecommendedFiling(filings)?.filing_type).toBe('10-Q')
  })

  it('does NOT prefer an annual report over a newer quarterly filing', () => {
    // Explicitly guards against regressing to the old "latest 10-K wins" behavior.
    const filings = [
      filing(1, '10-Q', '2026-04-29'),
      filing(2, '10-K', '2025-07-30'),
    ]
    expect(selectRecommendedFiling(filings)?.id).toBe(1)
  })

  it('recommends the 10-K when it genuinely is the most recent filing', () => {
    const filings = [
      filing(1, '10-Q', '2025-04-29'),
      filing(2, '10-K', '2025-07-30'),
    ]
    const rec = selectRecommendedFiling(filings)
    expect(rec?.id).toBe(2)
    expect(rec?.filing_type).toBe('10-K')
  })

  it('does not mutate the caller\'s array', () => {
    const filings = [filing(1, '10-K', '2025-07-30'), filing(2, '10-Q', '2026-04-29')]
    const before = filings.map((f) => f.id)
    selectRecommendedFiling(filings)
    expect(filings.map((f) => f.id)).toEqual(before)
  })

  it('returns null for empty, undefined, or null input', () => {
    expect(selectRecommendedFiling([])).toBeNull()
    expect(selectRecommendedFiling(undefined)).toBeNull()
    expect(selectRecommendedFiling(null)).toBeNull()
  })
})

describe('recommendedFilingNoun', () => {
  it('labels annual reports (10-K / 20-F / 40-F) as "annual report"', () => {
    expect(recommendedFilingNoun(filing(1, '10-K', '2025-07-30'))).toBe('annual report')
    expect(recommendedFilingNoun(filing(2, '20-F', '2025-07-30'))).toBe('annual report')
    expect(recommendedFilingNoun(filing(3, '40-F', '2025-07-30'))).toBe('annual report')
  })

  it('labels every other form as "filing"', () => {
    expect(recommendedFilingNoun(filing(1, '10-Q', '2026-04-29'))).toBe('filing')
    expect(recommendedFilingNoun(filing(2, '6-K', '2026-04-29'))).toBe('filing')
    expect(recommendedFilingNoun(filing(3, '8-K', '2026-04-29'))).toBe('filing')
  })
})
