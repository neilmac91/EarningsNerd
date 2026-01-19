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

    // Tabs should be present but disabled (indicated by title) when content is empty
    const guidanceTab = screen.getByText('Guidance').closest('button')
    expect(guidanceTab).toBeInTheDocument()
    expect(guidanceTab).toHaveAttribute('title', 'No data available in this filing')

    const liquidityTab = screen.getByText('Liquidity').closest('button')
    expect(liquidityTab).toBeInTheDocument()
    expect(liquidityTab).toHaveAttribute('title', 'No data available in this filing')
  })
})
