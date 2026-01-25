import React from 'react'
import { render, screen } from '@testing-library/react'
import SummarySections from '@/components/SummarySections'

describe('SummarySections additional accordions', () => {
  it('hides additional information tabs when accordions lack content and shows unavailable sections disclosure', () => {
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

    // Per execution plan: tabs should be HIDDEN (not disabled) when content is empty
    // Since all sections are empty, only the navigation should exist but with no tab buttons
    const guidanceTab = screen.queryByRole('button', { name: /guidance/i })
    expect(guidanceTab).not.toBeInTheDocument()

    const liquidityTab = screen.queryByRole('button', { name: /liquidity/i })
    expect(liquidityTab).not.toBeInTheDocument()

    // Per execution plan: Executive Summary must note unavailable sections
    // Unavailable sections should appear in the "Not included in this filing" disclosure
    expect(screen.getByText('Not included in this filing:')).toBeInTheDocument()
    expect(screen.getByText(/Guidance data was not available/i)).toBeInTheDocument()
    expect(screen.getByText(/Liquidity data was not available/i)).toBeInTheDocument()
  })
})
