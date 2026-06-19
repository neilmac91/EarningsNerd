import api from '@/lib/api/client'

// A single filing matched by EDGAR full-text search. Mirrors the backend
// `FullTextSearchHit` schema (backend/app/schemas/search.py).
export interface SearchHit {
  accession_no: string
  form: string | null
  filed_date: string | null
  period_ending: string | null
  cik: string | null
  company: string | null
  ticker: string | null
  document: string | null
  sec_url: string | null
  document_url: string | null
}

export interface SearchResponse {
  query: string
  total: number
  count: number
  hits: SearchHit[]
}

export interface FullTextSearchParams {
  q: string
  /** Comma-separated SEC form types, e.g. "10-K,10-Q,8-K". */
  forms?: string
  /** Earliest filing date, YYYY-MM-DD. */
  startdt?: string
  /** Latest filing date, YYYY-MM-DD. */
  enddt?: string
  /** Pagination offset (EDGAR caps deep pagination near 10,000). */
  from?: number
}

export const searchFullText = async (
  params: FullTextSearchParams,
): Promise<SearchResponse> => {
  const response = await api.get('/api/search/full-text', { params })
  return response.data
}
