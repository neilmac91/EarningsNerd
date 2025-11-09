import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SummarySections from '@/components/SummarySections'

const summaryBase = {
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

describe('Risk factors include supporting evidence', () => {
  it('filters out risks without evidence and renders those with citations', async () => {
    const summary = {
      ...summaryBase,
      raw_summary: {
        sections: {
          risk_factors: [
            {
              summary: 'Supply chain disruption remains elevated.',
              supporting_evidence: 'Item 1A: “Supply chain constraints persisted through Q3.”',
            },
            {
              summary: 'Generic statement with no evidence.',
            },
          ],
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    const user = userEvent.setup()
    const risksTab = screen.getByRole('button', { name: /risks/i })
    await act(async () => {
      await user.click(risksTab)
    })

    expect(
      screen.getByText('Supply chain disruption remains elevated.')
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Item 1A:/i)
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Generic statement with no evidence.')
    ).not.toBeInTheDocument()
  })
})


