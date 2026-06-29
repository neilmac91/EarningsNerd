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
  // false when the backend's reconciliation gate flagged this value (shown with a badge).
  reconciled: boolean
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

// Company-wide latest (`is_latest`) annual series — the company page's trend.
export const getFundamentals = async (ticker: string): Promise<FundamentalsResponse> => {
  const response = await api.get(`/api/companies/${encodeURIComponent(ticker)}/fundamentals`)
  return response.data
}

// Filing-scoped series — the multi-year figures *as reported in this specific filing* (roadmap B),
// served by GET /api/filings/{id}/fundamentals. Immutable snapshot, faithful to the document.
export const getFilingFundamentals = async (filingId: number): Promise<FundamentalsResponse> => {
  const response = await api.get(`/api/filings/${filingId}/fundamentals`)
  return response.data
}
