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

// Filing APIs
export const getCompanyFilings = async (
  ticker: string,
  filingTypes?: string,
  limit?: number
): Promise<Filing[]> => {
  const params: Record<string, string | number> = {}
  if (filingTypes) params.filing_types = filingTypes
  if (limit) params.limit = limit
  const response = await api.get(`/api/filings/company/${ticker}`, { params })
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
