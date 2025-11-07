import { render, screen } from '@testing-library/react'
import FinancialMetricsTable from '@/components/FinancialMetricsTable'
import FinancialCharts from '@/components/FinancialCharts'

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

  it('does not render the prior series in charts', () => {
    const { container } = render(<FinancialCharts metrics={metricsWithoutComparatives} />)
    expect(container.querySelector('[data-testid="prior-series"]')).toBeNull()
  })
})


