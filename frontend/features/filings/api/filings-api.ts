import api from '@/lib/api/client'

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

export const compareFilings = async (filingIds: number[]): Promise<ComparisonData> => {
  const response = await api.post('/api/compare', {
    filing_ids: filingIds,
  })
  return response.data
}
