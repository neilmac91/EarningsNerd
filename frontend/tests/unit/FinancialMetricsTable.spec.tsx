import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'

// Per-ADS block as the backend attaches it (value, ratio, currency, dated source, arithmetic).
const PER_ADS = {
  value: 45.6,
  ordinary_per_ads: 8,
  currency: 'CNY',
  as_of: '2026-06-28',
  source: 'Alibaba 20-F cover / deposit agreement — 1 ADS = 8 ordinary shares',
  arithmetic: 'CNY 5.7 per ordinary share × 8 = CNY 45.6 per ADS',
}

describe('FinancialMetricsTable — per-ADS EPS (item 1.5)', () => {
  it('renders the per-ADS figure + auditable arithmetic on an ADR EPS row', () => {
    const { container } = render(
      <FinancialMetricsTable
        metrics={[
          { metric: 'Diluted EPS', current_period: 'CN¥5.70', prior_period: 'CN¥5.50', per_ads: PER_ADS },
        ]}
      />,
    )
    // The per-ADS figure is shown (headline) ...
    expect(container).toHaveTextContent('per ADS')
    // ... alongside the full conversion arithmetic so it's auditable.
    expect(container).toHaveTextContent('CNY 5.7 per ordinary share × 8 = CNY 45.6 per ADS')
  })

  it('omits the per-ADS note for a domestic / non-ADR row', () => {
    const { container } = render(
      <FinancialMetricsTable
        metrics={[{ metric: 'Diluted EPS', current_period: '$7.46', prior_period: '$6.11' }]}
      />,
    )
    expect(container).not.toHaveTextContent('per ADS')
  })
})
