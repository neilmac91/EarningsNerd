import api from '@/lib/api/client'

/** A single filing matched by EDGAR full-text search (mirrors backend `FullTextSearchHit`). */
export interface FullTextSearchHit {
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

export interface FullTextSearchResponse {
  query: string
  total: number // total filings matching upstream (EDGAR caps deep pagination near 10,000)
  count: number // number of hits in this page
  hits: FullTextSearchHit[]
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
  params: FullTextSearchParams
): Promise<FullTextSearchResponse> => {
  const response = await api.get('/api/search/full-text', { params })
  return response.data
}
