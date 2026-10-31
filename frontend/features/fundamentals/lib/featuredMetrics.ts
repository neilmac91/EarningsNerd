/**
 * The metrics Financial trends offers, in its picker's order, each with its format. Pure and import-free, so the card
 * (FundamentalsTrendChart.tsx) and its mount gate read one list: the gate's answer offering every featured metric
 * (tests/e2e/filing-fundamentals-chart.spec.ts) is built from it, so each label is measured against the picker's one
 * width the moment it ships (E253).
 */
export type FmtKind = 'usd' | 'eps' | 'pct' | 'ratio'

// Curated, ordered set of concepts to offer (only those present in the response are shown).
// `concept` keys match the backend's standardized vocabulary (facts_service._CONCEPT_UNITS). Each label is stored in
// sentence case, as the picker, the tooltip, the values stop, the footnote and the source checks show it (E34).
export const FEATURED: { key: string; label: string; fmt: FmtKind }[] = [
  { key: 'revenue', label: 'Revenue', fmt: 'usd' },
  // Financial-institution revenue lines (only present for banks/insurers/BDCs — a bank shows these
  // instead of a single Revenue; insurers add these alongside their reported total revenue).
  { key: 'net_interest_income', label: 'Net interest income', fmt: 'usd' },
  { key: 'noninterest_income', label: 'Non-interest income', fmt: 'usd' },
  { key: 'premiums_earned', label: 'Premiums earned', fmt: 'usd' },
  { key: 'net_investment_income', label: 'Net investment income', fmt: 'usd' },
  { key: 'net_income', label: 'Net income', fmt: 'usd' },
  { key: 'gross_profit', label: 'Gross profit', fmt: 'usd' },
  { key: 'operating_income', label: 'Operating income', fmt: 'usd' },
  { key: 'operating_cash_flow', label: 'Operating cash flow', fmt: 'usd' },
  { key: 'investing_cash_flow', label: 'Investing cash flow', fmt: 'usd' },
  { key: 'financing_cash_flow', label: 'Financing cash flow', fmt: 'usd' },
  { key: 'free_cash_flow', label: 'Free cash flow', fmt: 'usd' },
  { key: 'eps_diluted', label: 'Diluted EPS', fmt: 'eps' },
  { key: 'earnings_per_share', label: 'EPS', fmt: 'eps' },
  { key: 'gross_margin', label: 'Gross margin', fmt: 'pct' },
  { key: 'operating_margin', label: 'Operating margin', fmt: 'pct' },
  { key: 'net_margin', label: 'Net margin', fmt: 'pct' },
  { key: 'total_assets', label: 'Total assets', fmt: 'usd' },
  { key: 'current_assets', label: 'Current assets', fmt: 'usd' },
  { key: 'current_liabilities', label: 'Current liabilities', fmt: 'usd' },
  { key: 'working_capital', label: 'Working capital', fmt: 'usd' },
  { key: 'current_ratio', label: 'Current ratio', fmt: 'ratio' },
  { key: 'shareholders_equity', label: "Shareholders' equity", fmt: 'usd' },
]
