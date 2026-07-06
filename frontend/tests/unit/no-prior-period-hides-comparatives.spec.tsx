import { render, screen } from '@testing-library/react'
import FinancialMetricsTable from '@/features/filings/components/FinancialMetricsTable'

const metricsWithoutComparatives = [
  {
    metric: 'Revenue',
    current_period: '$125,000',
    prior_period: '',
    commentary: 'Revenue grew on new customer wins.',
  },
  {
    metric: 'Gross Margin',
    current_period: '48%',
    prior_period: '',
    commentary: 'Margin expansion from pricing discipline.',
  },
]

describe('No prior period hides comparatives', () => {
  it('does not render prior/change columns in the metrics table', () => {
    render(<FinancialMetricsTable metrics={metricsWithoutComparatives} />)

    expect(screen.queryByText(/Prior Period/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Change/i)).not.toBeInTheDocument()
  })
})
