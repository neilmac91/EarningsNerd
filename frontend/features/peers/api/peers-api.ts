import api from '@/lib/api/client'
import type { FactProvenance } from '@/features/analysis/lib/provenance'

/** One company in a peers answer: the backend's `PeerEntry` (backend/app/schemas/peers.py), field for field. An entry has
 *  no link of its own: a reported value's is `provenance.source_url`, which Sources & checks reads.
 *  backend/tests/unit/test_peers_fixture_contract.py holds these fields to the schema's. */
export interface PeerEntry {
  ticker: string
  company_name: string
  /** Null where the value is withheld (a derived EPS: `provenance.validation` "unavailable"). */
  value: number | null
  period_end: string | null
  fiscal_year: number | null
  is_subject: boolean
  /** Competition rank over the companies with a value (ties share one); null for a withheld value. */
  rank: number | null
  percentile: number | null
  /** False where the value is not a passed check (`provenance.validation` other than "passed"). */
  reconciled: boolean
  provenance: FactProvenance | null
}

/** GET /api/companies/{ticker}/peers?metric={concept}: the backend's `PeerComparisonResponse`, field for field but `sic`,
 *  which no copy prints, so the client leaves it unread. `concept` is what the answer ranks on, which can differ from the
 *  metric asked (a bank asked for revenue answers net interest income); `peer_count` counts every entry, withheld ones
 *  included; `peers` is the whole cohort, the subject among them where it holds a fact, value descending. */
export interface PeerComparisonResponse {
  ticker: string
  company_name: string
  concept: string
  unit: string | null
  peer_count: number
  subject: PeerEntry
  peers: PeerEntry[]
}

/** A company ranked against the companies of its SEC industry code on one metric (a standardized concept). */
export const getPeers = async (ticker: string, metric: string): Promise<PeerComparisonResponse> => {
  const response = await api.get(`/api/companies/${encodeURIComponent(ticker)}/peers`, { params: { metric } })
  return response.data
}
