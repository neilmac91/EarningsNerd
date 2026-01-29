import api, { getApiUrl } from '@/lib/api/client'
import type { FinancialHighlights, RiskFactor } from '@/types/summary'
import { isApiError, getErrorStatus } from '@/lib/api/types'

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
    writer_error?: string
    writer?: {
      fallback_used?: boolean
      fallback_reason?: string
    }
    [key: string]: unknown
  } | null
}

export interface SummaryProgressData {
  stage: 'pending' | 'fetching' | 'parsing' | 'analyzing' | 'summarizing' | 'completed' | 'error'
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
export const generateSummary = async (filingId: number): Promise<Summary> => {
  const response = await api.post(`/api/summaries/filing/${filingId}/generate`)
  return response.data
}

export interface ProgressData {
  elapsed_seconds?: number
  heartbeat_count?: number
  percent?: number
}

export const generateSummaryStream = async (
  filingId: number,
  onChunk: (chunk: string) => void,
  onProgress: (stage: string, message: string, data?: ProgressData) => void,
  onComplete: (summaryId: number) => void,
  onError: (error: string) => void,
  options?: { force?: boolean }
): Promise<void> => {
  const apiUrl = getApiUrl()
  const forceParam = options?.force ? '?force=true' : ''
  const url = `${apiUrl}/api/summaries/filing/${filingId}/generate-stream${forceParam}`

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

  let response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    signal: controller.signal,
  })

  // Retry as guest on 401
  if (response.status === 401) {
    console.warn(`[summary] ${filingId} 401 Unauthorized. Retrying as guest...`)
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'omit',
      signal: controller.signal,
    })
  }

  if (!response.ok) {
    clearTimeoutSafely()

    // Handle authentication errors (if second attempt also failed or was not 401)
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
      throw new Error(errorMessage)
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
    throw new Error(errorMessage)
  }

  console.info(
    `[summary] ${filingId} stream opened in ${(performance.now() - streamStart).toFixed(1)} ms`
  )

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  if (!reader) {
    clearTimeoutSafely()
    throw new Error('No reader available')
  }

  resetTimeout()

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
              onChunk(data.content)
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
              onComplete(data.summary_id)
            } else if (data.type === 'error') {
              console.warn(`[summary] ${filingId} stream error: ${data.message}`)
              onError(data.message)
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
  } catch (error: unknown) {
    const errObj = error as { name?: string; message?: string }
    if (errObj?.name === 'AbortError') {
      const timeoutMessage = `Request timed out after ${STREAM_TIMEOUT_MS / 1000} seconds without activity.`
      onError(timeoutMessage)
      throw new Error(timeoutMessage)
    }
    onError(errObj?.message || 'Failed to generate summary stream.')
    throw error
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
  const response = await api.post('/api/saved-summaries', {
    summary_id: summaryId,
    notes,
  })
  return response.data
}

export const getSavedSummaries = async (): Promise<SavedSummary[]> => {
  const response = await api.get('/api/saved-summaries')
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
