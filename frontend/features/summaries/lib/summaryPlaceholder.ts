/**
 * A summary body that is interim or error filler ("Generating summary…", "Summary temporarily
 * unavailable", "requires OpenAI API key") rather than analysis. The tokens mirror the backend's one
 * home for them (backend/app/services/summary_placeholders.py, case-insensitive substrings), so the
 * company search's `summary_ready` and the company page's "summary ready" say the same thing;
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

/** A summary a reader can open now: a body that is neither empty nor placeholder filler, the rule
 *  the company search's `latest_filing.summary_ready` applies (latest_filing_service). */
export const isSummaryReady = (summary: { business_overview?: string | null } | null | undefined): boolean =>
  Boolean(summary?.business_overview?.trim()) && !isSummaryPlaceholder(summary?.business_overview)
