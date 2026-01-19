import axios from 'axios'
import type { FinancialHighlights, RiskFactor } from '../types/summary'

// Determine API URL: prefer env var, fallback based on environment
export const getApiUrl = () => {
  // Always use environment variable if set (for production deployments)
  if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL
  }
  // For client-side: check window location
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
      return 'http://localhost:8000'
    }
  }
  // For server-side: check NODE_ENV
  if (typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000'
  }
  // Default to production API
  return 'https://api.earningsnerd.io'
}

// Get the API URL - for client-side this will be determined at runtime
const getBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return getApiUrl()
  }
  // Server-side: use localhost in development
  return process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://api.earningsnerd.io'
}

// Create axios instance with baseURL
const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
  withCredentials: true,
})

// Set baseURL dynamically on each request (for client-side)
api.interceptors.request.use((config) => {
  // Always set baseURL dynamically to ensure correct URL in client-side
  if (typeof window !== 'undefined') {
    config.baseURL = getApiUrl()
  }
  return config
})

// Increased to 150 seconds (2.5 minutes) to accommodate backend retries with exponential backoff
const STREAM_TIMEOUT_MS = 150000

export interface StockQuote {
  price?: number
  change?: number
  change_percent?: number
  currency?: string
  pre_market_price?: number
  pre_market_change?: number
  pre_market_change_percent?: number
  post_market_price?: number
  post_market_change?: number
  post_market_change_percent?: number
}

export interface Company {
  id: number
  cik: string
  ticker: string
  name: string
  exchange?: string
  stock_quote?: StockQuote
}

export interface TrendingTicker {
  symbol: string
  name?: string | null
  tweet_volume?: number | null
  sentiment_score?: number | null
}

export interface TrendingTickerResponse {
  tickers: TrendingTicker[]
  source: string
  timestamp: string
  status?: string
  message?: string
}

export interface Filing {
  id: number
  filing_type: string
  filing_date: string
  report_date?: string
  accession_number: string
  document_url: string
  sec_url: string
  company?: {
    id: number
    ticker: string
    name: string
    exchange?: string
  }
}

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

// Company APIs
export const searchCompanies = async (query: string): Promise<Company[]> => {
  const response = await api.get('/api/companies/search', {
    params: { q: query },
  })
  return response.data
}

export const getCompany = async (ticker: string): Promise<Company> => {
  const response = await api.get(`/api/companies/${ticker}`)
  return response.data
}

export const getTrendingCompanies = async (limit: number = 10): Promise<Company[]> => {
  const response = await api.get('/api/companies/trending', {
    params: { limit },
  })
  return response.data
}

export const getTrendingTickers = async (): Promise<TrendingTickerResponse> => {
  const response = await api.get('/api/trending_tickers')
  return response.data
}

// Filing APIs
export const getCompanyFilings = async (
  ticker: string,
  filingTypes?: string
): Promise<Filing[]> => {
  const response = await api.get(`/api/filings/company/${ticker}`, {
    params: filingTypes ? { filing_types: filingTypes } : {},
  })
  return response.data
}

export const getFiling = async (filingId: number): Promise<Filing> => {
  const response = await api.get(`/api/filings/${filingId}`)
  return response.data
}

export const getRecentFilings = async (limit: number = 10): Promise<Filing[]> => {
  const response = await api.get('/api/filings/recent/latest', {
    params: { limit },
  })
  return response.data
}

// Summary APIs
export const generateSummary = async (filingId: number): Promise<Summary> => {
  const response = await api.post(`/api/summaries/filing/${filingId}/generate`)
  return response.data
}

export const generateSummaryStream = async (
  filingId: number,
  onChunk: (chunk: string) => void,
  onProgress: (stage: string, message: string) => void,
  onComplete: (summaryId: number) => void,
  onError: (error: string) => void
): Promise<void> => {
  const apiUrl = getApiUrl()
  const url = `${apiUrl}/api/summaries/filing/${filingId}/generate-stream`

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

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    signal: controller.signal,
  })

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
              recordStageTiming(stageName, message)
              onProgress(stageName, message)
            } else if (data.type === 'complete') {
              recordStageTiming('complete', 'summary ready')
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
      `[summary] ${filingId} stream closed after ${totalElapsed.toFixed(1)} ms${
        breakdown ? ` | stages ${breakdown}` : ''
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
    const axiosErr = error as { response?: { status?: number } }
    if (axiosErr.response?.status === 404) {
      return null
    }
    throw error
  }
}

export interface SummaryProgressData {
  stage: 'pending' | 'fetching' | 'parsing' | 'analyzing' | 'summarizing' | 'completed' | 'error'
  elapsedSeconds: number
}

export const getSummaryProgress = async (filingId: number): Promise<SummaryProgressData> => {
  const response = await api.get(`/api/summaries/filing/${filingId}/progress`)
  return response.data
}

// Auth APIs
export const register = async (email: string, password: string, fullName?: string) => {
  const response = await api.post('/api/auth/register', {
    email,
    password,
    full_name: fullName,
  })
  return response.data
}

export const login = async (email: string, password: string) => {
  const response = await api.post('/api/auth/login', {
    email,
    password,
  })
  return response.data
}

export const getCurrentUser = async () => {
  const response = await api.get('/api/auth/me')
  return response.data
}

export const getCurrentUserSafe = async () => {
  try {
    return await getCurrentUser()
  } catch (error: unknown) {
    const axiosErr = error as { response?: { status?: number } }
    if (axiosErr.response?.status === 401) {
      return null
    }
    throw error
  }
}

export const logout = async () => {
  const response = await api.post('/api/auth/logout')
  return response.data
}

// Subscription APIs
export interface Usage {
  summaries_used: number
  summaries_limit: number | null
  is_pro: boolean
  month: string
}

export interface SubscriptionStatus {
  is_pro: boolean
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  subscription_status: string | null
}

export const getUsage = async (): Promise<Usage> => {
  const response = await api.get('/api/subscriptions/usage')
  return response.data
}

export const getSubscriptionStatus = async (): Promise<SubscriptionStatus> => {
  const response = await api.get('/api/subscriptions/subscription')
  return response.data
}

export const createCheckoutSession = async (priceId: string): Promise<{ url: string }> => {
  const response = await api.post('/api/subscriptions/create-checkout-session', null, {
    params: { price_id: priceId }
  })
  return response.data
}

export const createPortalSession = async (): Promise<{ url: string }> => {
  const response = await api.post('/api/subscriptions/create-portal-session')
  return response.data
}

// Saved Summaries APIs
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

// Watchlist APIs
export interface WatchlistItem {
  id: number
  company_id: number
  created_at: string
  company: {
    id: number
    ticker: string
    name: string
  }
}

export const addToWatchlist = async (ticker: string): Promise<WatchlistItem> => {
  const response = await api.post(`/api/watchlist/${ticker}`)
  return response.data
}

export const getWatchlist = async (): Promise<WatchlistItem[]> => {
  const response = await api.get('/api/watchlist')
  return response.data
}

export interface WatchlistFilingInsight {
  id: number
  filing_type: string
  filing_date: string | null
  period_end_date: string | null
  summary_id: number | null
  summary_status: string
  summary_created_at: string | null
  summary_updated_at: string | null
  needs_regeneration: boolean
  progress?: {
    stage?: string
    elapsed?: number
    elapsedSeconds?: number
  } | null
}

export interface WatchlistInsight {
  company: {
    id: number
    ticker: string
    name: string
  }
  latest_filing: WatchlistFilingInsight | null
  total_filings: number
}

export const getWatchlistInsights = async (): Promise<WatchlistInsight[]> => {
  const response = await api.get('/api/watchlist/insights')
  return response.data
}

export const removeFromWatchlist = async (ticker: string): Promise<void> => {
  await api.delete(`/api/watchlist/${ticker}`)
}

// Comparison APIs
export interface ComparisonData {
  filings: Array<{
    id: number
    filing_type: string
    filing_date: string | null
    period_end_date: string | null
    company: {
      ticker: string
      name: string
    }
  }>
  comparison: {
    financial_metrics: Array<{
      filing_id: number
      metrics: Array<Record<string, unknown>>
    }>
    risk_factors: Array<{
      filing_id: number
      risks: Array<Record<string, unknown>>
    }>
    summary_count: number
  }
}

export const compareFilings = async (filingIds: number[]): Promise<ComparisonData> => {
  const response = await api.post('/api/compare', {
    filing_ids: filingIds,
  })
  return response.data
}

export default api

