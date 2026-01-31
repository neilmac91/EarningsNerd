import api from '@/lib/api/client'

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
  watchlist_count?: number | null
  price?: number | null
  change?: number | null
  change_percent?: number | null
  // Legacy fields for backward compatibility
  tweet_volume?: number | null
  sentiment_score?: number | null
}

export interface TrendingTickerResponse {
  tickers: TrendingTicker[]
  source: string
  timestamp: string
  status?: string
  message?: string
  filtered_count?: number
}

export interface PriceData {
  price?: number | null
  change?: number | null
  change_percent?: number | null
}

export interface PriceRefreshResponse {
  prices: Record<string, PriceData>
  timestamp: string
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

export const refreshTickerPrices = async (symbols: string[]): Promise<PriceRefreshResponse> => {
  const response = await api.post('/api/trending_tickers/refresh-prices', null, {
    params: { symbols },
    paramsSerializer: {
      indexes: null, // Use repeated params: ?symbols=AAPL&symbols=MSFT
    },
  })
  return response.data
}
