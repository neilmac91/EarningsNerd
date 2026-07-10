import api, { getApiUrl } from '@/lib/api/client'
import { refreshAccessToken } from '@/lib/api/refresh'
import type { FinancialHighlights, MetricItem, RiskFactor } from '@/types/summary'
import { isApiError, getErrorStatus } from '@/lib/api/types'
import posthog from 'posthog-js'

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

// Forwarded with the stream request so server-side funnel events
// (generation_started/succeeded/failed/timed_out) attach to the same PostHog
// person as the frontend events (summary_viewed, search, etc.).
const getPosthogDistinctId = (): string | null => {
  if (typeof window === 'undefined') return null
  try {
    return posthog.get_distinct_id() || null
  } catch {
    return null
  }
}

// Reduced to 120 seconds (2 minutes) to match backend pipeline timeout guarantee
// The heartbeat mechanism keeps the connection alive, but we now have a hard limit
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

  // Track whether the user has already seen real output. Once content is delivered we must
  // never silently retry (it would duplicate or reset their summary) — surface the error.
  let deliveredContent = false

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const result = await runStreamAttempt(filingId, onChunk, onProgress, onComplete, options, () => {
      deliveredContent = true
    })

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
    onProgress('initializing', 'Connection interrupted. Retrying...')
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
  markContentDelivered: () => void
): Promise<StreamAttemptResult> => {
  const apiUrl = getApiUrl()
  const params = new URLSearchParams()
  if (options?.force) params.set('force', 'true')
  if (options?.entryPoint) params.set('entry_point', options.entryPoint)
  const phId = getPosthogDistinctId()
  if (phId) params.set('ph_id', phId)
  const query = params.toString()
  const url = `${apiUrl}/api/summaries/filing/${filingId}/generate-stream${query ? `?${query}` : ''}`

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

  const postStream = () =>
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      signal: controller.signal,
    })

  let response = await postStream()

  // Expired access cookie: the shared axios client silently refreshes + replays on 401
  // (lib/api/client.ts), but this sanctioned raw SSE fetch bypasses it — so a user who idled past
  // ACCESS_TOKEN_EXPIRE_MINUTES would dead-end on "Could not validate credentials" with a Retry
  // that re-sends the same expired cookie forever. Mirror the client: one refresh, one replay.
  // (The old "retry as guest" fallback used to mask this; it died with guest generation.)
  if (response.status === 401) {
    try {
      await refreshAccessToken(apiUrl)
      response = await postStream()
    } catch {
      // Refresh failed — the session is genuinely gone; fall through to the 401 handling below
      // and surface the sign-in error.
    }
  }

  if (!response.ok) {
    clearTimeoutSafely()

    // Handle authentication errors
    if (response.status === 401) {
      let errorMessage = 'Authentication error occurred.'
      try {
        const errorData = await response.json()
        if (errorData.detail) {
          errorMessage = errorData.detail
        } else if (errorData.message) {
          errorMessage = errorData.message
        }
      } catch {
        // If response is not JSON, use default message
      }
      return { ok: false, retryable: false, error: errorMessage }
    }

    // Handle other HTTP errors
    let errorMessage = `Request failed with status ${response.status}`
    try {
      const errorData = await response.json()
      if (errorData.detail) {
        errorMessage = errorData.detail
      } else if (errorData.message) {
        errorMessage = errorData.message
      }
    } catch {
      // If response is not JSON, use status-based message
      if (response.status === 403) {
        errorMessage = 'You do not have permission to perform this action.'
      } else if (response.status === 429) {
        errorMessage = 'Rate limit exceeded. Please try again later.'
      } else if (response.status >= 500) {
        errorMessage = 'Server error. Please try again later.'
      }
    }
    // 5xx is transient (worth one retry); 403/429 and other 4xx are not.
    const retryable = response.status >= 500
    return { ok: false, retryable, error: errorMessage }
  }

  console.info(
    `[summary] ${filingId} stream opened in ${(performance.now() - streamStart).toFixed(1)} ms`
  )

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  if (!reader) {
    clearTimeoutSafely()
    return { ok: false, retryable: true, error: 'No reader available' }
  }

  resetTimeout()

  // An SSE 'error' event from the backend is captured here (not surfaced immediately) so the
  // caller can decide whether to retry before showing it to the user.
  let streamErrorMessage: string | null = null

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      resetTimeout()

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'chunk') {
              const chunkSize =
                typeof data.content === 'string' ? data.content.length : 0
              console.info(`[summary] ${filingId} chunk received (${chunkSize} chars)`)
              markContentDelivered()
              onChunk(data.content)
            } else if (data.type === 'preview') {
              // A5: progressive section reveal — a growing full-markdown render emitted while the
              // model streams. Routed through onChunk, which REPLACES the displayed text; the
              // authoritative final 'chunk' supersedes the last preview. No-op when the backend
              // feature flag is off (no preview events are emitted).
              if (typeof data.markdown === 'string' && data.markdown) {
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
          } catch (e) {
            console.error('Error parsing SSE data:', e)
          }
        }
      }
    }

    if (streamErrorMessage) {
      // Backend-emitted error mid-stream — transient by default; retry decision is the caller's.
      return { ok: false, retryable: true, error: streamErrorMessage }
    }
    return { ok: true, retryable: false, error: '' }
  } catch (error: unknown) {
    const errObj = error as { name?: string; message?: string }
    if (errObj?.name === 'AbortError') {
      const timeoutMessage = `Request timed out after ${STREAM_TIMEOUT_MS / 1000} seconds without activity.`
      return { ok: false, retryable: true, error: timeoutMessage }
    }
    return { ok: false, retryable: true, error: errObj?.message || 'Failed to generate summary stream.' }
  } finally {
    clearTimeoutSafely()
    controller.abort()
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
  display: string
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

export interface ChangeReport {
  has_prior: boolean
  comparison_basis: string | null
  prior_filing: PriorFilingRef | null
  metrics: WhatChangedMetrics | null
  risks: RiskDiff | null
  /** @deprecated T1.6: always null — the What-changed lead is now metrics.headline; kept for API compat. */
  key_changes: string | null
  has_changes: boolean
}

export const getWhatChanged = async (filingId: number): Promise<ChangeReport> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/what-changed`)
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
