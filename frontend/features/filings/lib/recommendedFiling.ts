import type { Filing } from '@/features/filings/api/filings-api'

// Annual reports: 10-K (domestic) plus the foreign-issuer equivalents 20-F / 40-F. Only used to
// LABEL the recommended filing ("annual report" vs "filing") — never to choose it. See
// tasks/fpi-support-roadmap.md.
export const ANNUAL_FILING_TYPES = ['10-K', '20-F', '40-F']

const byFilingDateDesc = (a: Filing, b: Filing) =>
  new Date(b.filing_date).getTime() - new Date(a.filing_date).getTime()

/**
 * The filing to spotlight in the "Recommended" banner: a company's single MOST RECENT filing of
 * ANY type. The honest starting point for a first-time visitor is the newest thing the company
 * actually filed. This deliberately does NOT prefer annual reports — the old logic pinned the
 * latest 10-K, which surfaced a stale annual report as "most recent" on any company that has
 * filed a 10-Q since (i.e. most of the year), making the banner read as inaccurate.
 *
 * Callers pass the FULL filing list (not the active type filter) so the recommendation stays
 * stable as the user filters. Returns null when there are no filings.
 */
export function selectRecommendedFiling(filings: Filing[] | undefined | null): Filing | null {
  return [...(filings ?? [])].sort(byFilingDateDesc)[0] ?? null
}

/**
 * The noun for the recommended-filing banner copy: an annual report reads as "annual report";
 * every other form (10-Q, 6-K, …) is just a "filing". Because the recommended filing is now the
 * most recent of any type, "annual report" only ever appears when that newest filing genuinely is
 * one — so the copy ("...'s most recent annual report") stays accurate.
 */
export function recommendedFilingNoun(filing: Filing): 'annual report' | 'filing' {
  return ANNUAL_FILING_TYPES.includes(filing.filing_type) ? 'annual report' : 'filing'
}
