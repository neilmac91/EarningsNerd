import api, { getApiUrl } from '@/lib/api/client'
import { postStreamWithRefresh } from '@/lib/api/streamRefresh'
import type { FinancialHighlights, MetricItem, RiskFactor } from '@/types/summary'
import { isApiError, getErrorStatus } from '@/lib/api/types'
import { getCookiePreferences } from '@/components/CookieConsent'

// --- Structured content projection (T2) ---------------------------------------------------------
// `rendered_sections` mirrors the backend's single source of truth
// (backend/app/services/summary_sections.py::render_sections -> Section.to_dict). It is the ONE
// projection the web renders — the same Section/Block list that feeds the PDF and CSV — so the
// three surfaces can never diverge. Computed on read from the ENRICHED raw_summary, so metric rows
// carry the server-computed deltas + provenance and risks carry their source traces.

// A `metrics` block's typed rows: MetricItem plus the server-computed delta cells (rule-12
// single-source — rendered verbatim, no client math). Shape matches FinancialMetricsTable's
// FinancialMetric so it feeds that component directly.
export type RenderedMetricRow = MetricItem & {
  change_display?: string | null
  change_direction?: 'up' | 'down' | 'flat' | null
  change_tone?: 'gain' | 'loss' | 'flat' | null
  // T4: server-verified citation for the row's Investor-Takeaway commentary (distinct from the XBRL
  // number provenance in MetricSourceLink — the number and the takeaway cite independently).
  commentary_evidence?: BlockEvidence | null
}

// Optional anchored citation for a block/claim {excerpt, section_ref, verified, fragment_url}, or null
// when the claim couldn't be located. Populated at read time in Tier 4.
export interface BlockEvidence {
  excerpt?: string | null
  section_ref?: string | null
  verified?: boolean | null
  fragment_url?: string | null
}

export type RenderedBlock = {
  kind: 'paragraph' | 'subheading' | 'quote' | 'bullets' | 'table' | 'metrics' | 'callout'
  text?: string
  speaker?: string
  label?: string
  items?: string[]
  headers?: string[]
  rows?: string[][]
  metric_rows?: RenderedMetricRow[]
  // Block-level citation (e.g. a management quote).
  evidence?: BlockEvidence
  // T4: per-row citations for a 'table' block (e.g. footnotes), parallel to `rows`; each entry is a
  // BlockEvidence or null.
  row_evidence?: (BlockEvidence | null)[]
}

export interface RenderedSection {
  id: string
  title: string
  blocks: RenderedBlock[]
  /** Stable machine role for specially-rendered sections (e.g. 'risks'); preferred over slug matching. */
  role?: string
  /** Management's disclosed/outlook sentiment, rendered as a Badge (T1.2 treatment), not prose. */
  tone?: string
}

// Bound the connect/refresh handshake and each period without stream activity.
// Heartbeats reset the read deadline; this is not a total generation deadline.
const STREAM_TIMEOUT_MS = 120000

export interface Summary {
  id: number
  filing_id: number
  business_overview?: string
  financial_highlights?: FinancialHighlights | null
  risk_factors?: RiskFactor[] | null
  management_discussion?: string
  key_changes?: string
  raw_summary?: {
    risk_source_context_version?: number
    sections?: Record<string, unknown>
    section_coverage?: {
      covered_count?: number
      total_count?: number
      coverage_ratio?: number
    }
    status?: string
    quality?: {
      tier?: string
      reasons?: string[]
    }
    writer_error?: string
    writer?: {
      fallback_used?: boolean
      fallback_reason?: string
    }
    [key: string]: unknown
  } | null
  // Structured Section/Block projection of the enriched raw_summary (T2). The ONE surface the web
  // renders; null on the empty-summary fallback, [] when a summary has no renderable sections.
  rendered_sections?: RenderedSection[] | null
}

export interface SummaryProgressData {
  // `partial` is a real terminal stage the backend writes (record_progress(..., "partial") on the
  // timeout / low-coverage path) — it was missing here, which is what stranded the L1 poll.
  stage: 'pending' | 'fetching' | 'parsing' | 'analyzing' | 'summarizing' | 'completed' | 'error' | 'partial'
  elapsedSeconds: number
}

export interface SavedSummary {
  id: number
  summary_id: number
  notes: string | null
  created_at: string
  summary: {
    id: number
    filing_id: number
    business_overview?: string
  }
  filing: {
    id: number
    filing_type: string
    filing_date: string | null
    period_end_date: string | null
  }
  company: {
    id: number
    ticker: string
    name: string
  }
}

// Summary APIs

export interface ProgressData {
  elapsed_seconds?: number
  heartbeat_count?: number
  percent?: number
}

// The free/guest summary quota was reached (the backend surfaces this as the stream error).
export const isPaywallStreamError = (message: string): boolean => {
  const m = (message || '').toLowerCase()
  return m.includes('monthly limit') || m.includes('upgrade to pro')
}

// Errors that must NOT be auto-retried: retrying can't help and would waste the user's time.
const isNonRetryableStreamError = (message: string): boolean => {
  const m = (message || '').toLowerCase()
  return (
    isPaywallStreamError(message) ||
    m.includes('permission') ||
    m.includes('sign in') ||
    m.includes('authentication')
  )
}

const STREAM_RETRY_BACKOFF_MS = 1200

export const generateSummaryStream = async (
  filingId: number,
  onChunk: (chunk: string) => void,
  onProgress: (stage: string, message: string, data?: ProgressData) => void,
  onComplete: (summaryId: number) => void,
  onError: (error: string) => void,
  options?: { force?: boolean; entryPoint?: string }
): Promise<void> => {
  const MAX_ATTEMPTS = 2 // one automatic retry before surfacing the error to the user
  // A random, in-memory action label; never used as an authorization or idempotency key.
  const logicalRequestId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID() : undefined

  // Track whether the user has already seen real output. Once content is delivered we must
  // never silently retry (it would duplicate or reset their summary) — surface the error.
  let deliveredContent = false

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const result = await runStreamAttempt(filingId, onChunk, onProgress, onComplete, options, () => {
      deliveredContent = true
    }, logicalRequestId, attempt)

    if (result.ok) return

    const canRetry =
      attempt < MAX_ATTEMPTS &&
      !deliveredContent &&
      result.retryable &&
      !isNonRetryableStreamError(result.error)

    if (!canRetry) {
      onError(result.error)
      throw new Error(result.error)
    }

    console.warn(`[summary] ${filingId} stream attempt ${attempt} failed (${result.error}); retrying once...`)
    onProgress('initializing', 'Connection interrupted. Trying again…')
    await new Promise((resolve) => setTimeout(resolve, STREAM_RETRY_BACKOFF_MS))
  }
}

interface StreamAttemptResult {
  ok: boolean
  retryable: boolean
  error: string
}

const runStreamAttempt = async (
  filingId: number,
  onChunk: (chunk: string) => void,
  onProgress: (stage: string, message: string, data?: ProgressData) => void,
  onComplete: (summaryId: number) => void,
  options: { force?: boolean; entryPoint?: string } | undefined,
  markContentDelivered: () => void,
  logicalRequestId: string | undefined,
  clientAttempt: number,
): Promise<StreamAttemptResult> => {
  const apiUrl = getApiUrl()
  const params = new URLSearchParams()
  if (options?.force) params.set('force', 'true')
  if (options?.entryPoint) params.set('entry_point', options.entryPoint)

  const controller = new AbortController()
  const streamStart = performance.now()
  const stageTimeline: Array<{ stage: string; at: number; delta: number; message: string }> = []
  let lastStageMark = streamStart
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  const recordStageTiming = (stageValue: string, message: string) => {
    const stage = stageValue || 'unknown'
    const now = performance.now()
    const delta = now - lastStageMark
    stageTimeline.push({ stage, at: now - streamStart, delta, message })
    lastStageMark = now
    const suffix = message ? ` - ${message}` : ''
    console.info(`[summary] ${filingId} stage ${stage} +${Math.round(delta)}ms${suffix}`)
  }

  const resetTimeout = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      controller.abort()
    }, STREAM_TIMEOUT_MS)
  }

  const clearTimeoutSafely = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  let transportAttempt = 0
  const postStream = () => {
    transportAttempt += 1
    // Re-read consent on every physical handshake, including an auth-refresh replay.
    const requestParams = new URLSearchParams(params)
    if (typeof window !== 'undefined' && getCookiePreferences()?.analytics === true) {
      requestParams.set('analytics_consent', 'true')
      if (logicalRequestId) requestParams.set('logical_request_id', logicalRequestId)
      requestParams.set('client_attempt', String(clientAttempt))
      requestParams.set('transport_attempt', String(transportAttempt))
    }
    const query = requestParams.toString()
    const url = `${apiUrl}/api/summaries/filing/${filingId}/generate-stream${query ? `?${query}` : ''}`
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      signal: controller.signal,
    })
  }

  // A refresh is shared with other requests and cannot be cancelled by this reader. Race the
  // whole handshake against our signal so a stalled refresh cannot strand this attempt; any
  // eventual replay still carries the aborted signal and cannot start another generation.
  const untilAborted = <T,>(operation: Promise<T>): Promise<T> =>
    new Promise((resolve, reject) => {
      const onAbort = () => reject(new DOMException('Summary stream timed out', 'AbortError'))
      controller.signal.addEventListener('abort', onAbort, { once: true })
      operation.then(
        (value) => {
          controller.signal.removeEventListener('abort', onAbort)
          resolve(value)
        },
        (error) => {
          controller.signal.removeEventListener('abort', onAbort)
          reject(error)
        },
      )
      if (controller.signal.aborted) onAbort()
    })

  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  let completed = false
  let streamErrorMessage: string | null = null

  const consumeLine = (line: string) => {
    if (!line.startsWith('data: ')) return
    let data
    try {
      data = JSON.parse(line.slice(6))
    } catch (error) {
      console.error('Error parsing SSE data:', error)
      return
    }
    if (!data || typeof data !== 'object') return

    if (data.type === 'chunk' && typeof data.content === 'string') {
      console.info(`[summary] ${filingId} chunk received (${data.content.length} chars)`)
      if (data.content) markContentDelivered()
      onChunk(data.content)
    } else if (data.type === 'preview') {
      // Previews are visible output too: retrying after one would silently replay generation.
      if (typeof data.markdown === 'string' && data.markdown) {
        markContentDelivered()
        onChunk(data.markdown)
      }
    } else if (data.type === 'progress') {
      const stageName = typeof data.stage === 'string' ? data.stage : 'unknown'
      const message = typeof data.message === 'string' ? data.message : ''
      const progressData: ProgressData = {
        elapsed_seconds: typeof data.elapsed_seconds === 'number' ? data.elapsed_seconds : undefined,
        heartbeat_count: typeof data.heartbeat_count === 'number' ? data.heartbeat_count : undefined,
        percent: typeof data.percent === 'number' ? data.percent : undefined,
      }
      recordStageTiming(stageName, message)
      onProgress(stageName, message, progressData)
    } else if (data.type === 'complete' || data.type === 'partial') {
      if (!Number.isSafeInteger(data.summary_id) || data.summary_id <= 0) {
        streamErrorMessage = 'The summary ended with an invalid completion. Try again.'
        return
      }
      completed = true
      recordStageTiming(data.type, data.message || 'summary ready')
      markContentDelivered()
      onComplete(data.summary_id)
    } else if (data.type === 'error') {
      console.warn(`[summary] ${filingId} stream error: ${data.message}`)
      streamErrorMessage = typeof data.message === 'string' ? data.message : 'Error generating summary'
    } else if (data.type === 'start') {
      const message = typeof data.message === 'string' ? data.message : ''
      recordStageTiming('start', message)
      onProgress('summarizing', message)
    }
  }

  resetTimeout()
  try {
    // Keep the existing silent 401 refresh/replay owner, with a bounded handshake.
    const response = await untilAborted(postStreamWithRefresh(postStream))
    if (!response.ok) {
      // The reader's sentence when the response carries no detail of its own. A 401 is never retried
      // whatever its text (retryable is set only for a 5xx below); its sentence says what to do.
      let errorMessage = response.status === 401
        ? 'Sign in again to generate this summary.'
        : 'The summary could not start. Try again.'
      try {
        const errorData = await untilAborted(response.json())
        if (typeof errorData?.detail === 'string') errorMessage = errorData.detail
        else if (typeof errorData?.message === 'string') errorMessage = errorData.message
      } catch (error) {
        if (controller.signal.aborted) throw error
        // "permission" stays in the 403 sentence: it is the one place the word isNonRetryableStreamError tests
        // for is written (no backend message on this route says it), and the matcher gates hold each of its
        // phrases to a writer (tests/unit/streamErrorCopy.spec.ts). A 403 is never retried in any case.
        if (response.status === 403) errorMessage = 'Your account does not have permission to generate this summary.'
        else if (response.status === 429) errorMessage = 'Too many summary requests just now. Try again shortly.'
        else if (response.status >= 500) errorMessage = 'The server could not start the summary. Try again in a moment.'
      }
      return { ok: false, retryable: response.status >= 500, error: errorMessage }
    }

    console.info(
      `[summary] ${filingId} stream opened in ${(performance.now() - streamStart).toFixed(1)} ms`
    )
    reader = response.body?.getReader()
    if (!reader) return { ok: false, retryable: true, error: 'The connection dropped before the summary started. Try again.' }

    const decoder = new TextDecoder()
    let buffer = ''
    resetTimeout()
    while (!completed && streamErrorMessage === null) {
      const { done, value } = await untilAborted(reader.read())
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      // A complete JSON frame at EOF is still usable even without its final newline.
      if (done && buffer) lines.push(buffer)
      for (const line of lines) {
        consumeLine(line)
        if (completed || streamErrorMessage !== null) break
      }
      if (done) break
      resetTimeout()
    }

    if (streamErrorMessage !== null) {
      return { ok: false, retryable: true, error: streamErrorMessage }
    }
    if (!completed) {
      return {
        ok: false,
        retryable: true,
        error: 'The connection closed before the summary finished. Try again.',
      }
    }
    return { ok: true, retryable: false, error: '' }
  } catch (error: unknown) {
    // The card prints this result's error, so it is a sentence in the product voice, never the transport's
    // own text ("Failed to fetch", "Load failed", "NetworkError when attempting to fetch resource."); the
    // transport's text goes to the console. Both are retryable, so no matcher phrase is involved.
    const errObj = error as { name?: string; message?: string }
    if (errObj?.name === 'AbortError') {
      return {
        ok: false,
        retryable: true,
        error: `The summary timed out after ${STREAM_TIMEOUT_MS / 1000} seconds without progress. Try again.`,
      }
    }
    console.warn(`[summary] ${filingId} stream transport failed: ${errObj?.message ?? String(error)}`)
    return { ok: false, retryable: true, error: 'The connection dropped before the summary finished. Try again.' }
  } finally {
    clearTimeoutSafely()
    controller.abort()
    // Cancel without waiting for transport cleanup; the request deadline must stay bounded.
    void reader?.cancel?.().catch(() => undefined)
    reader?.releaseLock?.()
    const totalElapsed = performance.now() - streamStart
    const breakdown = stageTimeline
      .map(({ stage, at, delta }) => `${stage}:${Math.round(at)}ms (Δ${Math.round(delta)}ms)`)
      .join(', ')
    console.info(
      `[summary] ${filingId} stream closed after ${totalElapsed.toFixed(1)} ms${breakdown ? ` | stages ${breakdown}` : ''
      }`
    )
  }
}

export const getSummary = async (filingId: number): Promise<Summary | null> => {
  try {
    const response = await api.get(`/api/summaries/filing/${filingId}`)
    // Return null if summary is empty/not generated yet
    if (response.data && !response.data.business_overview) {
      return null
    }
    return response.data
  } catch (error: unknown) {
    // If 404 or other error, return null instead of throwing
    if (isApiError(error) && getErrorStatus(error) === 404) {
      return null
    }
    throw error
  }
}

export const getSummaryProgress = async (filingId: number): Promise<SummaryProgressData> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/progress`)
  return response.data
}

// Saved Summaries APIs
export const saveSummary = async (summaryId: number, notes?: string): Promise<SavedSummary> => {
  // Trailing slash required — see getWatchlist: the slashless form 307-redirects to an
  // http:// Location behind the Cloud Run proxy, which the browser blocks as mixed content.
  const response = await api.post('/api/saved-summaries/', {
    summary_id: summaryId,
    notes,
  })
  return response.data
}

export const getSavedSummaries = async (): Promise<SavedSummary[]> => {
  const response = await api.get('/api/saved-summaries/')
  return response.data
}

export const getSavedSummaryStatus = async (summaryId: number): Promise<{ is_saved: boolean }> => {
  const response = await api.get(`/api/saved-summaries/status/${summaryId}`)
  return response.data
}

export const deleteSavedSummary = async (savedSummaryId: number): Promise<void> => {
  await api.delete(`/api/saved-summaries/${savedSummaryId}`)
}

export const updateSavedSummary = async (savedSummaryId: number, notes: string): Promise<SavedSummary> => {
  const response = await api.put(`/api/saved-summaries/${savedSummaryId}`, null, {
    params: { notes },
  })
  return response.data
}

// --- A5: "What Changed" period-over-period change report ---

export interface WhatChangedMetricItem {
  metric: string
  label: string
  direction: 'up' | 'down' | 'flat'
  pct: number | null
  current: number
  prior: number | null
  // Server-computed display string (one delta policy) + design-system tone; rendered verbatim.
  // null when the prior is zero: no percentage is meaningful, so only the direction is served.
  display: string | null
  tone: 'gain' | 'loss' | 'flat'
}

export interface WhatChangedMetrics {
  headline: string
  items: WhatChangedMetricItem[]
  data_quality: 'ok' | 'partial'
}

export interface RiskDiff {
  new: string[]
  resolved: string[]
  carried_count: number
}

export interface PriorFilingRef {
  filing_id: number
  filing_type: string
  filing_date: string | null
  period_end_date: string | null
}

/** One word-level edit inside a modified paragraph; equal segments carry the later filing's typography.
 *  Segments carry no edge spaces: join them with one space to read the paragraph. */
export type WordOp = ['equal' | 'delete' | 'insert', string]

/** One change of Item 1A against the prior same-form original, in the later filing's reading order.
 *  `id` is content-addressed (a stable key; repeated content is numbered). A modified paragraph
 *  carries only its word ops: the later text is the equal and insert segments, the prior text the
 *  equal and delete segments. */
export type SectionChange =
  | { id: string; kind: 'modified'; index: number; prior_index: number; similarity: number; moved: boolean; ops: WordOp[] }
  | { id: string; kind: 'added'; index: number; after: string }
  | { id: string; kind: 'removed'; prior_index: number; before: string }
  | { id: string; kind: 'moved'; index: number; prior_index: number; after: string }

export interface SectionSide {
  status: string
  extracted_at: string | null
  /** A 10-Q whose Item 1A only refers back to the annual report's risk factors (nothing restated). */
  reference_only: boolean
  char_count: number | null
  paragraph_count: number | null
}

export interface SectionChangesFilingRef extends PriorFilingRef {
  accession_number: string
}

interface SectionChangesBase {
  section: 'item_1a'
  section_label: string
  /** What this viewer got: the counts and the first items (`truncated`), or every item. */
  access: 'teaser' | 'full'
  engine_version: number
  /** The filing the section is compared against, whenever one exists. */
  prior_filing: SectionChangesFilingRef | null
}

export interface SectionChangesOk extends SectionChangesBase {
  status: 'ok'
  reason: null
  current: SectionSide
  prior: SectionSide
  paragraphs: { prior: number; later: number; prior_excluded: number; later_excluded: number }
  counts: { unchanged: number; modified: number; added: number; removed: number; moved: number }
  words: { later_total: number; inserted: number; deleted: number; changed_ratio: number }
  has_changes: boolean
  items: SectionChange[]
  items_total: number
  truncated: boolean
}

export interface SectionChangesNotOk extends SectionChangesBase {
  /** `pending`: a side is not extracted yet and the hourly batch will extract it; `no_prior`: no earlier
   *  same-form original; `unavailable`: nothing to compare as things stand (`reason` says why:
   *  form_not_supported, current_<status>, prior_<status>, or a side with no row that the batch will not
   *  select: current_outside_window / prior_outside_window, current_outside_cohort / prior_outside_cohort). */
  status: 'pending' | 'no_prior' | 'unavailable'
  reason: string
  current?: SectionSide
  prior?: SectionSide
}

/** The filing-text wording diff of the change report (Item 1A against the prior same-form original),
 *  served behind ENABLE_SECTION_CHANGES: null while the feature is off, and absent from a sample or
 *  an older backend. */
export type SectionChanges = SectionChangesOk | SectionChangesNotOk

export interface ChangeReport {
  has_prior: boolean
  comparison_basis: string | null
  prior_filing: PriorFilingRef | null
  metrics: WhatChangedMetrics | null
  /** The filer's as-filed reporting currency ("USD", "JPY", an ISO 4217 code): every metric item's
   *  current/prior amount is in it. Null (or absent, from an older backend) when unknown. */
  reporting_currency?: string | null
  risks: RiskDiff | null
  /** @deprecated T1.6: always null — the What-changed lead is now metrics.headline; kept for API compat. */
  key_changes: string | null
  /** XBRL deltas exist (the metrics block); the wording diff has its own state in `section_changes`. */
  has_changes: boolean
  section_changes?: SectionChanges | null
}

export const getWhatChanged = async (filingId: number): Promise<ChangeReport> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/what-changed`)
  return response.data
}

// --- The Pro review of the wording changes (E27, PR B) -----------------------------------------
// A reader labels each change of the section_changes list `reviewed` or `follow_up`; the review is
// complete when every change carries a label, and the server then freezes a receipt naming the
// two texts compared. Both endpoints are Pro-only (403 otherwise); labels hang on the changes'
// content-addressed ids. Read through features/summaries/hooks/useWordingReview.

export type WordingLabel = 'reviewed' | 'follow_up'

export interface WordingReceipt {
  version: number
  completed_at: string
  section: 'item_1a'
  section_label: string
  filing: SectionChangesFilingRef
  prior_filing: SectionChangesFilingRef
  texts: {
    current: { sha256: string | null; extractor_version: number | null; extracted_at: string | null }
    prior: { sha256: string | null; extractor_version: number | null; extracted_at: string | null }
  }
  engine_version: number
  app_version: string
  paragraphs: SectionChangesOk['paragraphs']
  counts: SectionChangesOk['counts']
  words: SectionChangesOk['words']
  items_total: number
  labels: { reviewed: number; follow_up: number }
  follow_up_ids: string[]
}

export interface WordingReviewState {
  filing_id: number
  section: 'item_1a'
  section_label: string
  /** `unavailable`: nothing to review yet (no comparison, or the feature is off); no items then. */
  status: 'ok' | 'unavailable'
  engine_version: number
  items_total: number
  /** Change id to label, for the changes of the current comparison only. */
  labels: Record<string, WordingLabel>
  counts: { reviewed: number; follow_up: number; unlabeled: number }
  /** Set while every change is labelled and the receipt still describes the live comparison. */
  completed_at: string | null
  receipt: WordingReceipt | null
  /** On a label's answer only: this label completed the queue (the transition the completion event counts). */
  completed_now?: boolean
}

export const getWordingReview = async (filingId: number): Promise<WordingReviewState> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/wording-review`)
  return response.data
}

export const setWordingLabel = async (
  filingId: number,
  itemId: string,
  label: WordingLabel | null,
): Promise<WordingReviewState> => {
  const response = await api.put(`/api/summaries/filing/${filingId}/wording-review/labels`, { item_id: itemId, label })
  return response.data
}

// Summary exports (Pro). Routed through the shared axios client so they inherit
// auth/refresh + `withCredentials` (replacing the page's two raw `fetch()`s).
// A non-Pro caller gets a 403 the shared error layer surfaces via getErrorStatus.
export const exportSummaryPdf = async (filingId: number): Promise<Blob> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/export/pdf`, {
    responseType: 'blob',
  })
  return response.data
}

export const exportSummaryCsv = async (filingId: number): Promise<Blob> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/export/csv`, {
    responseType: 'blob',
  })
  return response.data
}
