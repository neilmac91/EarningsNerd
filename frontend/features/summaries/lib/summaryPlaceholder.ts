import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { stripLeadingExecutiveHeading } from '@/lib/stripLeadingExecutiveHeading'

/**
 * A summary body that is interim or error filler ("Generating summary…", "Summary temporarily
 * unavailable", "requires OpenAI API key") rather than analysis. The tokens mirror the backend's one
 * home for them (backend/app/services/summary_placeholders.py, case-insensitive substrings);
 * tests/unit/summaryPlaceholder.spec.ts holds the two lists equal.
 */
export const SUMMARY_PLACEHOLDER_TOKENS = [
  'generating summary',
  'summary temporarily unavailable',
  'requires openai api key',
] as const

export const isSummaryPlaceholder = (text: string | null | undefined): boolean => {
  const lowered = (text ?? '').toLowerCase()
  return SUMMARY_PLACEHOLDER_TOKENS.some((token) => lowered.includes(token))
}

/** The body the pipeline stores in place of a summary it could not write. */
export const SUMMARY_FALLBACK_MESSAGE = 'Summary temporarily unavailable. Please retry.'

/** The markdown the filing page renders: the internal notices, then a leading "Executive Summary"
 *  heading, stripped (the page's card title is the one header). */
export const cleanSummaryMarkdown = (markdown: string): string =>
  stripLeadingExecutiveHeading(stripInternalNotices(markdown))

type StoredSummary = { business_overview?: string | null; raw_summary?: unknown } | null | undefined

/**
 * A stored summary that failed, which the filing page shows as its "Summary temporarily unavailable"
 * card instead of the body: a writer error, the fallback body, or nothing left once the notices are
 * stripped. SummaryDisplay decides its error card with it, so readiness below is that page's own rule.
 */
export const isSummaryFailure = (summary: StoredSummary): boolean => {
  const raw = summary?.raw_summary && typeof summary.raw_summary === 'object' ? (summary.raw_summary as { writer_error?: unknown }) : null
  const body = cleanSummaryMarkdown(summary?.business_overview ?? '').trim()
  return Boolean(raw?.writer_error) || body === SUMMARY_FALLBACK_MESSAGE || body.length === 0
}

/** A summary a reader can open now: the filing page shows its body, and the body is not placeholder
 *  filler, so the company page's "summary ready" never promises a summary that page will not show.
 *  The company search's `latest_filing.summary_ready` (latest_filing_service) applies the same rule
 *  server-side, so a result and the lead it opens agree. */
export const isSummaryReady = (summary: StoredSummary): boolean =>
  !isSummaryPlaceholder(summary?.business_overview) && !isSummaryFailure(summary)
