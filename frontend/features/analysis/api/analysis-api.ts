import api, { getApiUrl } from '@/lib/api/client'

// Idle timeout for the SSE stream — mirrors copilot-api.ts: any activity resets the clock.
const STREAM_TIMEOUT_MS = 120000

// --- Types (mirror the backend /api/analysis contract) ---

export type AnalysisMode = 'annual' | 'quarterly'

export interface AnnualCoveragePeriod {
  key: string // "FY2024"
  fiscal_year: number
  period_end: string
  has_core: boolean
}

export interface QuarterlyCoveragePeriod {
  key: string // "2024Q2"
  fiscal_year: number
  fiscal_period: string
  period_end: string
  /** True when every value in the column is Q4-derived (FY − Q1..Q3) — badged in the picker. */
  derived: boolean
}

export interface AnalysisCoverage {
  ticker: string
  company_name: string
  supported: boolean
  reason: 'ifrs_filer' | 'no_facts' | null
  /** First-touch SEC sync still running server-side — retry shortly. */
  syncing: boolean
  synced_at: string | null
  annual: AnnualCoveragePeriod[]
  quarterly: QuarterlyCoveragePeriod[]
  limits: { annual: number; quarterly: number }
}

/** "nm" = the YoY/QoQ comparison crossed zero (a sign flip) and isn't a meaningful percentage —
 *  finance convention "n/m", rendered as such rather than a nonsensical number. */
export type GrowthValue = number | 'nm'

export interface AnalysisPoint {
  period: string
  value: number | null
  unit?: string
  period_end?: string
  form?: string | null
  accession?: string
  raw_tag?: string | null
  derived?: boolean
  reconciled?: boolean
  /** For a `percent`-unit series (margins), already a percentage-POINT delta — do not ×100 and
   *  do not treat as relative growth. Every other series: relative growth as a fraction. */
  yoy?: GrowthValue | null
  qoq?: GrowthValue | null
  marker?: string
  fiscal_year?: number
  fiscal_period?: string
}

export interface AnalysisSeries {
  concept: string
  label: string
  unit: string
  /** Values are ×100 percentages (margins) — render "24.3%", not "$24.30"; YoY/QoQ deltas on
   *  these series are percentage points, not relative growth (see AnalysisPoint.yoy). */
  percent: boolean
  cagr: number | null
  /** Percentage-point change over the series' valued endpoints (annual mode, `percent` series
   *  only) — the CAGR counterpart for a percentage, where compounding doesn't apply. */
  window_pp?: number | null
  window_pp_range?: string | null
  points: AnalysisPoint[]
}

export interface AnalysisInflection {
  kind: string
  concepts?: string[]
  periods?: string[]
  detail: string
  markers?: string[]
}

export interface AnalysisDataset {
  ticker: string
  company_name: string
  mode: AnalysisMode
  period_key: string
  periods: { key: string; fiscal_year: number; fiscal_period: string; period_end: string }[]
  series: AnalysisSeries[]
  inflections: AnalysisInflection[]
}

/** Same shape as CopilotCitation — the citation chips/Sources UI renders both. */
export interface AnalysisCitation {
  n: number
  excerpt: string
  section_ref: string | null
  verified: boolean
  fragment_url: string | null
  concept?: string
  value?: number
  period?: string
  derived?: boolean
}

export interface AnalysisCompletion {
  kind: 'analysis' | 'not_enough_data'
  analysis_id: number | null
  narrative: string
  citations: AnalysisCitation[]
  grounded: number
  /** F# references the model emitted that did NOT resolve against the dataset (0 on a clean
   *  run; null/absent on rows persisted before the counter existed). */
  unverified?: number | null
  cached: boolean
  n_periods: number
}

export interface AnalysisRange {
  mode: AnalysisMode
  start_period: string
  end_period: string
}

export interface AnalysisStreamHandlers {
  onProgress?: (stage: string) => void
  onToken: (text: string) => void
  onComplete: (completion: AnalysisCompletion) => void
  onError: (message: string) => void
}

/** 403/429 gate errors — the UI swaps Retry for an Upgrade CTA (retrying can't help). */
export const isAnalysisPaywallError = (message: string): boolean => {
  const m = (message || '').toLowerCase()
  return m.includes('pro feature') || m.includes('upgrade to pro') || m.includes('fair-use limit')
}

// --- REST calls ---

export const getAnalysisCoverage = async (ticker: string): Promise<AnalysisCoverage> => {
  const response = await api.get(`/api/analysis/${encodeURIComponent(ticker)}/coverage`)
  return response.data
}

export const getAnalysisDataset = async (
  ticker: string,
  range: AnalysisRange
): Promise<AnalysisDataset> => {
  const response = await api.post(`/api/analysis/${encodeURIComponent(ticker)}/dataset`, range)
  return response.data
}

/** URL for the Pro PDF export of a completed analysis (fetched with credentials, blob download). */
export const analysisPdfUrl = (analysisId: number): string =>
  `${getApiUrl()}/api/analysis/export/${analysisId}/pdf`

const parseErrorDetail = async (response: Response, fallback: string): Promise<string> => {
  try {
    const data = await response.json()
    if (data?.detail) return typeof data.detail === 'string' ? data.detail : fallback
    if (data?.message) return typeof data.message === 'string' ? data.message : fallback
  } catch {
    // Non-JSON body — fall through to the status-based fallback.
  }
  return fallback
}

/**
 * Stream the AI trend narrative. Clone of copilot-api.askFilingStream (fetch POST +
 * credentials:'include', reader + TextDecoder, `data:` line parsing, idle timeout,
 * requestAnimationFrame token coalescing) against POST /api/analysis/{ticker}/stream.
 */
export const streamAnalysis = async (
  ticker: string,
  range: AnalysisRange & { force?: boolean },
  handlers: AnalysisStreamHandlers,
  signal?: AbortSignal
): Promise<void> => {
  const url = `${getApiUrl()}/api/analysis/${encodeURIComponent(ticker)}/stream`

  const controller = new AbortController()
  const onAbort = () => controller.abort()
  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener('abort', onAbort, { once: true })
    }
  }

  let timeoutId: ReturnType<typeof setTimeout> | null = null
  const resetTimeout = () => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS)
  }
  const clearTimeoutSafely = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  // Token coalescing — at most one onToken delivery per animation frame (see copilot-api.ts for
  // the full rationale: per-token markdown re-parses were O(n²) jank on long answers).
  let tokenBuffer = ''
  let rafId: number | null = null
  const canRaf = typeof requestAnimationFrame === 'function'
  const deliverBuffer = () => {
    rafId = null
    if (!tokenBuffer) return
    const text = tokenBuffer
    tokenBuffer = ''
    try {
      handlers.onToken(text)
    } catch (error) {
      controller.abort()
      handlers.onError(error instanceof Error ? error.message : 'Something went wrong displaying the analysis.')
    }
  }
  const enqueueToken = (text: string) => {
    if (!canRaf) {
      handlers.onToken(text)
      return
    }
    tokenBuffer += text
    if (rafId === null) rafId = requestAnimationFrame(deliverBuffer)
  }
  const cancelScheduledFlush = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }
  const discardBufferedTokens = () => {
    cancelScheduledFlush()
    tokenBuffer = ''
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        mode: range.mode,
        start_period: range.start_period,
        end_period: range.end_period,
        force: range.force ?? false,
      }),
      signal: controller.signal,
    })

    if (!response.ok) {
      let errorMessage: string
      if (response.status === 401) {
        errorMessage = 'Sign in to run an analysis.'
      } else if (response.status === 403) {
        errorMessage = await parseErrorDetail(response, 'Multi-Period Analysis is a Pro feature.')
      } else if (response.status === 429) {
        errorMessage = await parseErrorDetail(response, 'Monthly limit reached. Please try again later.')
      } else if (response.status >= 500) {
        errorMessage = await parseErrorDetail(response, 'Server error. Please try again.')
      } else {
        errorMessage = await parseErrorDetail(response, `Request failed with status ${response.status}`)
      }
      handlers.onError(errorMessage)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      handlers.onError('No response stream available.')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    resetTimeout()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      resetTimeout()
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const payload = line.slice(line.indexOf(':') + 1).trim()
        if (!payload) continue
        let data: Record<string, unknown>
        try {
          data = JSON.parse(payload)
        } catch (e) {
          console.error('[analysis] failed to parse SSE data:', e)
          continue
        }

        switch (data.type) {
          case 'progress':
            handlers.onProgress?.(typeof data.stage === 'string' ? data.stage : 'working')
            break
          case 'token':
            if (typeof data.text === 'string') enqueueToken(data.text)
            break
          case 'complete':
            // The completion carries the authoritative (renumbered) narrative — buffered raw
            // tokens are superseded.
            discardBufferedTokens()
            handlers.onComplete({
              kind: data.kind === 'not_enough_data' ? 'not_enough_data' : 'analysis',
              analysis_id: typeof data.analysis_id === 'number' ? data.analysis_id : null,
              narrative: typeof data.narrative === 'string' ? data.narrative : '',
              citations: Array.isArray(data.citations) ? (data.citations as AnalysisCitation[]) : [],
              grounded: typeof data.grounded === 'number' ? data.grounded : 0,
              unverified: typeof data.unverified === 'number' ? data.unverified : null,
              cached: data.cached === true,
              n_periods: typeof data.n_periods === 'number' ? data.n_periods : 0,
            })
            break
          case 'error':
            discardBufferedTokens()
            handlers.onError(typeof data.message === 'string' ? data.message : 'Something went wrong.')
            break
          default:
            break
        }
      }
    }

    // Graceful end-of-stream: flush any tail (only matters if the stream ended without a
    // terminal event — complete/error already discarded the buffer).
    cancelScheduledFlush()
    deliverBuffer()
  } catch (error: unknown) {
    const errObj = error as { name?: string; message?: string }
    if (errObj?.name === 'AbortError') {
      return
    }
    handlers.onError(errObj?.message || 'Network error. Please check your connection and try again.')
  } finally {
    clearTimeoutSafely()
    cancelScheduledFlush()
    signal?.removeEventListener('abort', onAbort)
  }
}
