import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { stripLeadingExecutiveHeading } from '@/lib/stripLeadingExecutiveHeading'

/**
 * Whether the filing page shows a stored summary's body: one rule for the page's display, its
 * metadata, the hero example and the company lead, mirroring the backend's single home for it
 * (backend/app/services/summary_placeholders.py: is_summary_ready, which the sitemap and the company
 * search apply).
 * tests/unit/summaryPlaceholder.spec.ts holds the tokens and the marker equal to the backend's.
 */
export const SUMMARY_PLACEHOLDER_TOKENS = [
  'generating summary',
  'summary temporarily unavailable',
  'requires openai api key',
] as const

/** The in-progress marker an earlier pipeline stored mid-run, matched case-sensitively as the filing
 *  page and the sitemap always have, so prose about "generating summary reports" stays content.
 *  useSummaryGeneration treats a body carrying it as no summary and starts the run. */
export const IN_PROGRESS_MARKER = 'Generating summary'

/** The other tokens mark a stored failure (SUMMARY_FAILURE_TOKENS). Real analysis never carries them. */
const FAILURE_TOKENS = SUMMARY_PLACEHOLDER_TOKENS.filter((token) => token !== 'generating summary')

/** Failure filler: a body carrying a failure token, in any case ("requires OpenAI API key" is operator
 *  configuration, never text for a reader). */
export const isFailureFiller = (text: string | null | undefined): boolean => {
  const lowered = (text ?? '').toLowerCase()
  return FAILURE_TOKENS.some((token) => lowered.includes(token))
}

/** The body the pipeline stores in place of a summary it could not write, and the filing page's
 *  error card copy. */
export const SUMMARY_FALLBACK_MESSAGE = 'Summary temporarily unavailable. Please retry.'

/** The markdown the filing page renders: the internal notices, then a leading "Executive Summary"
 *  heading, stripped (the page's card title is the one header). */
export const cleanSummaryMarkdown = (markdown: string): string =>
  stripLeadingExecutiveHeading(stripInternalNotices(markdown))

type StoredSummary = { business_overview?: string | null; raw_summary?: unknown } | null | undefined

/**
 * A stored summary the filing page shows as its "Summary temporarily unavailable" card, with Retry,
 * instead of the body: failure filler (the fallback body among it), a writer error, or nothing left
 * once the notices are stripped. SummaryDisplay decides its error card with it.
 */
export const isSummaryFailure = (summary: StoredSummary): boolean => {
  const raw = summary?.raw_summary
  const writerError = raw && typeof raw === 'object' ? (raw as { writer_error?: unknown }).writer_error : undefined
  return (
    isFailureFiller(summary?.business_overview) ||
    Boolean(writerError) ||
    cleanSummaryMarkdown(summary?.business_overview ?? '').trim().length === 0
  )
}

/** A summary a reader can open now: the filing page shows its body (no failure, no in-progress marker),
 *  so the company page's "summary ready" never promises a summary that page will not show. The company
 *  search's `latest_filing.summary_ready` (latest_filing_service) applies the backend's is_summary_ready,
 *  so a result and the lead it opens agree. */
export const isSummaryReady = (summary: StoredSummary): boolean =>
  !isSummaryFailure(summary) && !(summary?.business_overview ?? '').includes(IN_PROGRESS_MARKER)
