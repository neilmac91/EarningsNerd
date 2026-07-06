import api from '@/lib/api/client'

export interface FilingContent {
  filingId: number
  hasContent: boolean
  markdownContent: string | null
}

/**
 * Fetch a filing's cached full-text markdown for the in-app filing viewer (P7).
 *
 * Hits `GET /api/filings/{id}/content`. Returns `hasContent: false` (markdown null) when the filing
 * exists but has no cached markdown yet — the viewer then falls back to the SEC deep link. Throws on
 * 404 / network error so the caller can show an error state.
 */
export const fetchFilingContent = async (filingId: number): Promise<FilingContent> => {
  // Shared axios client (F4): plain JSON GET — no streaming/ISR justification for raw fetch,
  // and the client centralizes base URL + error shaping (throws on non-2xx like the old !ok path).
  const response = await api.get(`/api/filings/${filingId}/content`)
  const data = response.data
  return {
    filingId: typeof data.filing_id === 'number' ? data.filing_id : filingId,
    hasContent: data.has_content === true,
    markdownContent: typeof data.markdown_content === 'string' ? data.markdown_content : null,
  }
}
