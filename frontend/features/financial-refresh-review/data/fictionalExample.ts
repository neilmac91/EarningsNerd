import type { RefreshRow, SampleFact } from '../lib/refreshReview'

function fact(metric: string, label: string, value: number | null, newer = false): SampleFact {
  return {
    company: 'fictional-harbor-components', metric, label, value,
    periodStart: '2024-01-01', periodEnd: '2024-12-31', unit: 'USD', context: 'consolidated annual',
    sourceId: newer ? 'SAMPLE-2025-ANNUAL' : 'SAMPLE-2024-ANNUAL',
    filedOn: newer ? '2026-02-12' : '2025-02-10',
  }
}

export const FICTIONAL_ROWS: readonly RefreshRow[] = [
  { id: 'revenue', baseline: fact('revenue', 'Revenue', 125000000), candidate: fact('revenue', 'Revenue', 123000000, true) },
  { id: 'capex', baseline: fact('capex', 'Capital expenditure', 8000000), candidate: fact('capex', 'Capital expenditure', 8000000, true) },
  { id: 'net-income', baseline: fact('net_income', 'Net income', 14000000), candidate: { ...fact('net_income', 'Net income', 17000000, true), periodStart: '2025-01-01', periodEnd: '2025-12-31' } },
  { id: 'cash', baseline: { ...fact('cash', 'Cash', 19000000), periodStart: null }, candidate: { ...fact('cash', 'Cash', null, true), periodStart: null } },
  { id: 'expenses', baseline: fact('expenses', 'Operating expenses', 42000000), candidate: { ...fact('expenses', 'Operating expenses', 40000000, true), unit: 'EUR' } },
  { id: 'charges', baseline: fact('charges', 'Restructuring charges', 2000000), candidate: fact('charges', 'Restructuring charges', 0, true) },
]
