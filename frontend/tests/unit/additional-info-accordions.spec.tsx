import React from 'react'
import { render, screen } from '@testing-library/react'
import SummarySections from '@/components/SummarySections'

describe('SummarySections additional accordions', () => {
  it('hides additional information when accordions lack content', () => {
    const summary = {
      business_overview: '',
      raw_summary: {
        sections: {
          executive_snapshot: '',
          financial_highlights: {},
          risk_factors: [],
          management_discussion_insights: '',
          guidance_outlook: {},
          liquidity_capital_structure: {},
          notable_footnotes: {},
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // Tabs should not appear when content is empty
    expect(screen.queryByText('Guidance & Drivers')).not.toBeInTheDocument()
    expect(screen.queryByText('Liquidity & Covenants')).not.toBeInTheDocument()
  })
})
