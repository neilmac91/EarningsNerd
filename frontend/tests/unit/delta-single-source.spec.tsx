import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'

/**
 * Rule-12 machine gate for T1.5: the client renders ONLY the server-computed `change_display` and
 * does no delta math of its own. Behavioral (robust to refactors), so "delete client calculateChange"
 * stays enforced, not just prose.
 */
describe('delta single-source (T1.5)', () => {
  it('shows "—" when the API provides no change_display, even with current+prior present', () => {
    // If any client-side fallback computation existed, it would derive a % from 100 vs 80 here.
    const { container } = render(
      <FinancialMetricsTable
        metrics={[{ metric: 'Revenue', current_period: '$100', prior_period: '$80' }]}
      />,
    )
    expect(container).toHaveTextContent('—')
    expect(container).not.toHaveTextContent('%')
  })

  it('renders an API change string a relative-% formula could never produce', () => {
    const { container } = render(
      <FinancialMetricsTable
        metrics={[
          {
            metric: 'Gross Margin',
            current_period: '74.9%',
            prior_period: '60.5%',
            change_display: '+99.9 ppts',
            change_direction: 'up',
            change_tone: 'gain',
          },
        ]}
      />,
    )
    // The number comes only from the API: no formula over 74.9/60.5 yields +99.9.
    expect(container).toHaveTextContent('+99.9 ppts')
  })
})
