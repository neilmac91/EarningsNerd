import api from '@/lib/api/client'

// Mirrors the backend `InsiderActivityResponse` (backend/app/schemas/insiders.py),
// served by GET /api/companies/{ticker}/insiders?window_days={n}.
// A type alias (not an interface) so rows satisfy DataTable's
// `T extends Record<string, unknown>` constraint via the implied index signature.
export type InsiderTransaction = {
  insider_name: string | null
  insider_title: string | null
  is_director: boolean | null
  is_officer: boolean | null
  is_ten_pct_owner: boolean | null
  ticker: string | null
  transaction_date: string | null
  transaction_code: string | null
  transaction_label: string | null
  shares: number | null
  price: number | null
  value: number | null
  acquired_disposed: string | null // 'A' (acquired/buy) | 'D' (disposed/sell)
  is_10b5_1: boolean | null
  accession: string | null
  filed_date: string | null
}

export interface InsiderActivitySummary {
  window_days: number
  buy_count: number
  sell_count: number
  buy_shares: number
  sell_shares: number
  buy_value: number | null
  sell_value: number | null
  net_shares: number
  net_value: number | null
  discretionary_net_shares: number
  plan_10b5_1_sell_shares: number
  last_transaction_date: string | null
}

/** How far the stored Form 4 scan behind the answer has got (backend `InsiderScanState`, ADR 0009). The endpoint reads
 *  only the database, so a company's first visit answers `scanning` with nothing read yet, and trades arrive over the
 *  next minute or so, newest first. */
export interface InsiderScan {
  // complete: every listed filing is read. scanning: filings are still being read. paused: SEC pushed back and the
  // scan waits, then resumes on its own. failed: it cannot run for this company.
  status: 'complete' | 'scanning' | 'paused' | 'failed'
  /** Form 4 filings the scan knows of. */
  filings_listed: number
  /** Of those, how many have been read so far. */
  filings_read: number
  /** ISO date of the earliest filing read: how far back the stored trades reach. */
  oldest_filed_date: string | null
  /** ISO timestamp of the last listing. */
  refreshed_at: string | null
  /** When asking again can show more; null when nothing is pending. A `complete` scan can carry one (an hourly
   *  refresh under way behind complete data): the data still reads as complete. */
  retry_after_seconds: number | null
}

export interface InsiderActivityResponse {
  ticker: string
  company_name: string | null
  cik: string | null
  window_days: number
  summary: InsiderActivitySummary
  transactions: InsiderTransaction[]
  total_transactions: number
  scan: InsiderScan
}

export const getInsiderActivity = async (
  ticker: string,
  windowDays = 90,
): Promise<InsiderActivityResponse> => {
  const response = await api.get(`/api/companies/${encodeURIComponent(ticker)}/insiders`, {
    params: { window_days: windowDays },
  })
  return response.data
}
