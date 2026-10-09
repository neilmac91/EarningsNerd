import type { Filing } from '@/features/filings/api/filings-api'
import { baseForm, isAmendment, periodKind } from '@/features/filings/lib/filingPeriod'

// Newest filed first. A same-day tie (several 6-Ks, a same-day amendment) goes to the higher id, the
// rule the company search's latest filing uses (latest_filing_service), so a search result names the
// filing this page leads with whatever order the list arrives in.
const byFilingDateDesc = (a: Filing, b: Filing) =>
  new Date(b.filing_date).getTime() - new Date(a.filing_date).getTime() || b.id - a.id

/**
 * The filing the company page leads with ("Latest filing" in its identity lead, the target of its
 * one primary action, the "Latest" row marker): a company's single MOST RECENT filing of ANY type. The honest starting point for a first-time visitor is the newest thing the company
 * actually filed. This deliberately does NOT prefer annual reports — the old logic pinned the
 * latest 10-K, which surfaced a stale annual report as "most recent" on any company that has
 * filed a 10-Q since (i.e. most of the year), making the lead read as inaccurate.
 *
 * Callers pass the FULL filing list (not the active type filter) so the recommendation stays
 * stable as the user filters. Superseded originals remain in history but are not recommended.
 * Amendments are eligible on their actual filing date. Returns null when none are eligible.
 *
 * FPI policy: 20-F / 6-K / 40-F are already enabled. Active foreign issuers often file 6-Ks,
 * so this newest-filing policy can recommend an interim release ahead of the annual 20-F.
 * A future policy refinement may prefer substantive reports, but excluding 6-K must also change
 * the lead's "Latest filing" to "Latest report"; a hidden newer filing must never make the
 * recommendation's recency claim misleading.
 */
export function selectRecommendedFiling(filings: Filing[] | undefined | null): Filing | null {
  return (filings ?? []).filter((filing) => !filing.superseded_by_accession).sort(byFilingDateDesc)[0] ?? null
}

/** The period of report as a sortable day ("2025-09-27"); the wire may carry a full ISO instant. */
const reportDay = (filing: Filing) => (filing.report_date ?? '').slice(0, 10)

/**
 * The filing the company page's "Compare periods" card reports on (2026-10 critique, 1b): the newest
 * ANNUAL report (10-K, 20-F, 40-F) with a period of report, provided the list also holds an earlier
 * annual period of the same form. The change report compares a filing with its prior same-form
 * period and needs the filing's period to find one (change_report_service), so without that pair
 * there is no card rather than a card that can only say there is nothing to compare.
 *
 * Within the newest period, a filing that still stands beats a superseded one, and the original
 * beats a later amendment: a Part III 10-K/A carries no financial statements to compare.
 */
export function selectComparisonFiling(filings: Filing[] | undefined | null): Filing | null {
  const annual = (filings ?? []).filter((filing) => periodKind(filing.filing_type) === 'annual' && reportDay(filing))
  const rank = (filing: Filing) =>
    [reportDay(filing), filing.superseded_by_accession ? '0' : '1', isAmendment(filing.filing_type) ? '0' : '1', filing.filing_date].join(' ')
  const pick = [...annual].sort((a, b) => rank(b).localeCompare(rank(a)))[0]
  if (!pick) return null
  const hasEarlier = annual.some(
    (filing) => baseForm(filing.filing_type) === baseForm(pick.filing_type) && reportDay(filing) < reportDay(pick),
  )
  return hasEarlier ? pick : null
}
