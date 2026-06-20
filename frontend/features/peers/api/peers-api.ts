import api from '@/lib/api/client'

// Mirrors the backend `PeerComparisonResponse` (backend/app/schemas/peers.py),
// served by GET /api/companies/{ticker}/peers?metric={concept}.
export interface PeerEntry {
  ticker: string
  company_name: string
  value: number | null
  period_end: string | null
  fiscal_year: number | null
  is_subject: boolean
  rank: number | null
  percentile: number | null
  // false when the backend's reconciliation gate flagged this value (shown with a badge).
  reconciled: boolean
}

export interface PeerComparisonResponse {
  ticker: string
  company_name: string
  sic: string | null
  concept: string
  unit: string | null
  peer_count: number
  subject: PeerEntry
  peers: PeerEntry[]
}

export const getPeers = async (
  ticker: string,
  metric = 'revenue',
): Promise<PeerComparisonResponse> => {
  const response = await api.get(`/api/companies/${encodeURIComponent(ticker)}/peers`, {
    params: { metric },
  })
  return response.data
}
