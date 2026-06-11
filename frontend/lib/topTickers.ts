/**
 * Local-first search seed: the most-searched US mega/large-cap tickers.
 * Lets CompanySearch show instant matches before the network responds —
 * the full SEC ticker universe still comes from the API.
 * Tickers use SEC EDGAR notation (e.g. BRK-B).
 */
export interface TopTicker {
  ticker: string
  name: string
}

export const TOP_TICKERS: readonly TopTicker[] = [
  { ticker: 'AAPL', name: 'Apple Inc.' },
  { ticker: 'MSFT', name: 'Microsoft Corporation' },
  { ticker: 'NVDA', name: 'NVIDIA Corporation' },
  { ticker: 'GOOGL', name: 'Alphabet Inc.' },
  { ticker: 'AMZN', name: 'Amazon.com, Inc.' },
  { ticker: 'META', name: 'Meta Platforms, Inc.' },
  { ticker: 'TSLA', name: 'Tesla, Inc.' },
  { ticker: 'BRK-B', name: 'Berkshire Hathaway Inc.' },
  { ticker: 'AVGO', name: 'Broadcom Inc.' },
  { ticker: 'LLY', name: 'Eli Lilly and Company' },
  { ticker: 'JPM', name: 'JPMorgan Chase & Co.' },
  { ticker: 'V', name: 'Visa Inc.' },
  { ticker: 'UNH', name: 'UnitedHealth Group Incorporated' },
  { ticker: 'XOM', name: 'Exxon Mobil Corporation' },
  { ticker: 'WMT', name: 'Walmart Inc.' },
  { ticker: 'MA', name: 'Mastercard Incorporated' },
  { ticker: 'PG', name: 'The Procter & Gamble Company' },
  { ticker: 'JNJ', name: 'Johnson & Johnson' },
  { ticker: 'COST', name: 'Costco Wholesale Corporation' },
  { ticker: 'ORCL', name: 'Oracle Corporation' },
  { ticker: 'HD', name: 'The Home Depot, Inc.' },
  { ticker: 'ABBV', name: 'AbbVie Inc.' },
  { ticker: 'BAC', name: 'Bank of America Corporation' },
  { ticker: 'MRK', name: 'Merck & Co., Inc.' },
  { ticker: 'CVX', name: 'Chevron Corporation' },
  { ticker: 'KO', name: 'The Coca-Cola Company' },
  { ticker: 'AMD', name: 'Advanced Micro Devices, Inc.' },
  { ticker: 'PEP', name: 'PepsiCo, Inc.' },
  { ticker: 'NFLX', name: 'Netflix, Inc.' },
  { ticker: 'ADBE', name: 'Adobe Inc.' },
  { ticker: 'CRM', name: 'Salesforce, Inc.' },
  { ticker: 'TMO', name: 'Thermo Fisher Scientific Inc.' },
  { ticker: 'WFC', name: 'Wells Fargo & Company' },
  { ticker: 'CSCO', name: 'Cisco Systems, Inc.' },
  { ticker: 'ACN', name: 'Accenture plc' },
  { ticker: 'ABT', name: 'Abbott Laboratories' },
  { ticker: 'LIN', name: 'Linde plc' },
  { ticker: 'MCD', name: "McDonald's Corporation" },
  { ticker: 'DIS', name: 'The Walt Disney Company' },
  { ticker: 'INTU', name: 'Intuit Inc.' },
  { ticker: 'IBM', name: 'International Business Machines Corporation' },
  { ticker: 'GE', name: 'GE Aerospace' },
  { ticker: 'CAT', name: 'Caterpillar Inc.' },
  { ticker: 'QCOM', name: 'QUALCOMM Incorporated' },
  { ticker: 'AXP', name: 'American Express Company' },
  { ticker: 'VZ', name: 'Verizon Communications Inc.' },
  { ticker: 'AMGN', name: 'Amgen Inc.' },
  { ticker: 'INTC', name: 'Intel Corporation' },
  { ticker: 'GS', name: 'The Goldman Sachs Group, Inc.' },
  { ticker: 'BA', name: 'The Boeing Company' },
] as const

/** Instant matches: ticker prefix first, then name substring. Max `limit`. */
export const matchTopTickers = (query: string, limit = 6): TopTicker[] => {
  const q = query.trim().toLowerCase()
  if (!q) return []
  const byTicker = TOP_TICKERS.filter((t) => t.ticker.toLowerCase().startsWith(q))
  const byName = TOP_TICKERS.filter(
    (t) => !t.ticker.toLowerCase().startsWith(q) && t.name.toLowerCase().includes(q)
  )
  return [...byTicker, ...byName].slice(0, limit)
}
