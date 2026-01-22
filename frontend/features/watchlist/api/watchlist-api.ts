import api from '@/lib/api/client'

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

// Watchlist APIs
export const addToWatchlist = async (ticker: string): Promise<WatchlistItem> => {
  const response = await api.post(`/api/watchlist/${ticker}`)
  return response.data
}

export const getWatchlist = async (): Promise<WatchlistItem[]> => {
  const response = await api.get('/api/watchlist')
  return response.data
}

export const getWatchlistInsights = async (): Promise<WatchlistInsight[]> => {
  const response = await api.get('/api/watchlist/insights')
  return response.data
}

export const removeFromWatchlist = async (ticker: string): Promise<void> => {
  await api.delete(`/api/watchlist/${ticker}`)
}
