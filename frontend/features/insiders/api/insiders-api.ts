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

export interface InsiderActivityResponse {
  ticker: string
  company_name: string | null
  cik: string | null
  window_days: number
  summary: InsiderActivitySummary
  transactions: InsiderTransaction[]
  total_transactions: number
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
