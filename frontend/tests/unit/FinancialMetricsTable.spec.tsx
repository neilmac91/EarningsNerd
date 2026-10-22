import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'

// Per-ADS block as the backend attaches it (value, ratio, currency, dated source, arithmetic).
const PER_ADS = {
  value: 45.6,
  ordinary_per_ads: 8,
  currency: 'CNY',
  as_of: '2026-06-28',
  source: 'Alibaba 20-F cover / deposit agreement: 1 ADS = 8 ordinary shares',
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
    // The ratio source is a visible line, in the registry's own words.
    expect(container).toHaveTextContent(
      'Ratio source: Alibaba 20-F cover / deposit agreement: 1 ADS = 8 ordinary shares · as of 2026-06-28',
    )
    expect(container.textContent).not.toContain('\u2014')
  })

  it('reads a ratio source cached before the registry took the colon with the same colon', () => {
    // xbrl_data caches the registry's source, so a summary generated before E45 still carries its em-dash.
    const cached = { ...PER_ADS, source: 'Alibaba 20-F cover / deposit agreement \u2014 1 ADS = 8 ordinary shares' }
    const { container } = render(
      <FinancialMetricsTable
        metrics={[{ metric: 'Diluted EPS', current_period: 'CN¥5.70', prior_period: 'CN¥5.50', per_ads: cached }]}
      />,
    )
    expect(container).toHaveTextContent(
      'Ratio source: Alibaba 20-F cover / deposit agreement: 1 ADS = 8 ordinary shares · as of 2026-06-28',
    )
    expect(container.textContent).not.toContain('\u2014')
  })

  it('omits the per-ADS note for a domestic / non-ADR row', () => {
    const { container } = render(
      <FinancialMetricsTable
        metrics={[{ metric: 'Diluted EPS', current_period: '$7.46', prior_period: '$6.11' }]}
      />,
    )
    expect(container).not.toHaveTextContent('per ADS')
  })

  it('renders the server-computed change string verbatim (ppts for a margin), no client math', () => {
    const { container } = render(
      <FinancialMetricsTable
        metrics={[
          {
            metric: 'Operating Margin',
            current_period: '74.9%',
            prior_period: '60.5%',
            change_display: '+14.4 ppts',
            change_direction: 'up',
            change_tone: 'gain',
          },
        ]}
      />,
    )
    expect(container).toHaveTextContent('+14.4 ppts')
  })
})
