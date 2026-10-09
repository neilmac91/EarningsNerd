import { describe, expect, it } from 'vitest'
import {
  selectComparisonFiling,
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
  it('excludes superseded originals and keeps amendments eligible without inventing replacements', () => {
    const original = { ...filing(1, '10-K', '2026-06-01'), superseded_by_accession: 'not-loaded' }
    const amendment = filing(2, '10-K/A', '2026-05-01')
    expect(selectRecommendedFiling([original, amendment])?.id).toBe(2)
    expect(selectRecommendedFiling([original])).toBeNull()
    expect(selectRecommendedFiling([amendment, filing(3, '10-Q', '2026-05-02')])?.id).toBe(3)
  })

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

describe('selectComparisonFiling', () => {
  const annual = (id: number, form: string, filed: string, report: string, extra: Partial<Filing> = {}): Filing => ({
    ...filing(id, form, filed),
    report_date: `${report}T00:00:00+00:00`,
    ...extra,
  })

  it('picks the newest annual report when an earlier annual period of the same form is listed', () => {
    const filings = [
      filing(1, '10-Q', '2026-05-01'),
      annual(2, '10-K', '2025-10-31', '2025-09-27'),
      annual(3, '10-K', '2024-11-01', '2024-09-28'),
    ]
    expect(selectComparisonFiling(filings)?.id).toBe(2)
  })

  it('returns null without an earlier annual period to compare with', () => {
    expect(selectComparisonFiling([annual(2, '10-K', '2025-10-31', '2025-09-27'), filing(1, '10-Q', '2026-05-01')])).toBeNull()
    // A same-period amendment is not an earlier period.
    expect(selectComparisonFiling([annual(2, '10-K', '2025-10-31', '2025-09-27'), annual(4, '10-K/A', '2026-01-20', '2025-09-27')])).toBeNull()
    // Nor is another form's annual report.
    expect(selectComparisonFiling([annual(2, '10-K', '2025-10-31', '2025-09-27'), annual(5, '20-F', '2024-04-01', '2023-12-31')])).toBeNull()
  })

  it('needs a period of report: the change report cannot find a prior period without one', () => {
    expect(selectComparisonFiling([filing(2, '10-K', '2025-10-31'), annual(3, '10-K', '2024-11-01', '2024-09-28')])).toBeNull()
  })

  it('prefers the original over a later amendment of the same period', () => {
    const filings = [
      annual(4, '10-K/A', '2026-01-20', '2025-09-27'),
      annual(2, '10-K', '2025-10-31', '2025-09-27'),
      annual(3, '10-K', '2024-11-01', '2024-09-28'),
    ]
    expect(selectComparisonFiling(filings)?.id).toBe(2)
  })

  it('prefers the amendment that supersedes the original', () => {
    const filings = [
      annual(2, '10-K', '2025-10-31', '2025-09-27', { superseded_by_accession: 'acc-4' }),
      annual(4, '10-K/A', '2026-01-20', '2025-09-27'),
      annual(3, '10-K', '2024-11-01', '2024-09-28'),
    ]
    expect(selectComparisonFiling(filings)?.id).toBe(4)
  })

  it('covers the foreign-issuer annual forms, and tolerates empty input', () => {
    expect(selectComparisonFiling([annual(6, '20-F', '2026-04-01', '2025-12-31'), annual(7, '20-F', '2025-04-01', '2024-12-31')])?.id).toBe(6)
    expect(selectComparisonFiling([])).toBeNull()
    expect(selectComparisonFiling(undefined)).toBeNull()
    expect(selectComparisonFiling(null)).toBeNull()
  })
})
