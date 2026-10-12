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

/** The filing a search result leads to (backend latest_filing_service): the newest stored filing of
 *  the forms the company's filings list serves that still stands, and whether its summary is ready. */
export interface LatestFilingRef {
  id: number
  filing_type: string
  filing_date: string | null
  report_date: string | null
  summary_ready: boolean
}

export interface Company {
  id: number
  cik: string
  ticker: string
  name: string
  exchange?: string
  stock_quote?: StockQuote
  /** Search results only; absent when no such filing is stored yet. */
  latest_filing?: LatestFilingRef | null
  // Set to 'unsupported_foreign' for a recognizable foreign name (unsponsored ADR) that files no
  // financial reports with the SEC — the page renders an honest "coverage unavailable" state.
  coverage_status?: string
  coverage_reason?: string
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
