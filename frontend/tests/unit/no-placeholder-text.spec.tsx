import { render, screen } from '@testing-library/react'
import FinancialMetricsTable from '@/components/FinancialMetricsTable'
import SummarySections from '@/components/SummarySections'

describe('UI avoids placeholder copy', () => {
  it('does not render "Not available" placeholders', () => {
    const metrics = [
      {
        metric: 'Operating Cash Flow',
        current_period: '$42,000',
        prior_period: '',
        commentary: '',
      },
    ]

    const summary = {
      business_overview: '',
      raw_summary: {
        sections: {
          executive_snapshot: '',
          financial_highlights: {},
          risk_factors: [],
          management_discussion_insights: '',
        },
      },
    }

    render(
      <>
        <FinancialMetricsTable metrics={metrics} />
        <SummarySections summary={summary as any} metrics={metrics} />
      </>
    )

    expect(screen.queryByText(/Not available/i)).not.toBeInTheDocument()
  })
})


