import api from '@/lib/api/client'

// Mirrors the backend `FundamentalsResponse` (backend/app/schemas/fundamentals.py),
// served by GET /api/companies/{ticker}/fundamentals from the financial_fact table.
export interface FundamentalPoint {
  period_end: string | null
  fiscal_year: number | null
  fiscal_period: string | null
  value: number | null
  unit: string
  form: string | null
  accession: string
}

export interface FundamentalSeries {
  concept: string
  unit: string
  points: FundamentalPoint[]
}

export interface FundamentalsResponse {
  ticker: string
  company_name: string
  concepts: FundamentalSeries[]
}

export const getFundamentals = async (ticker: string): Promise<FundamentalsResponse> => {
  const response = await api.get(`/api/companies/${encodeURIComponent(ticker)}/fundamentals`)
  return response.data
}
