import React from 'react'
import { render, screen } from '@testing-library/react'
import SummarySections from '@/components/SummarySections'

describe('SummarySections renderMarkdownValue gating', () => {
  it('hides additional accordions when renderMarkdownValue yields blank strings and shows unavailable sections disclosure', () => {
    const summary = {
      business_overview: '',
      raw_summary: {
        sections: {
          guidance_outlook: ['', null, ''],
          liquidity_capital_structure: {
            liquidity: '',
            leverage: null,
            shareholder_returns: ['', null],
          },
          notable_footnotes: [
            { item: '', impact: '' },
          ],
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // Per execution plan: tabs should be HIDDEN (not disabled) when content is empty
    const guidanceTab = screen.queryByRole('button', { name: /guidance/i })
    expect(guidanceTab).not.toBeInTheDocument()

    const liquidityTab = screen.queryByRole('button', { name: /liquidity/i })
    expect(liquidityTab).not.toBeInTheDocument()

    // Per execution plan: Executive Summary must note unavailable sections
    expect(screen.getByText('Not included in this filing:')).toBeInTheDocument()
    expect(screen.getByText(/Guidance data was not available/i)).toBeInTheDocument()
    expect(screen.getByText(/Liquidity data was not available/i)).toBeInTheDocument()
  })

  it('shows additional accordions when renderMarkdownValue returns real content', () => {
    const summary = {
      business_overview: '',
      raw_summary: {
        sections: {
          guidance_outlook: {
            guidance: 'Management reiterated full-year outlook.',
            drivers: ['Demand recovery in core markets'],
          },
          liquidity_capital_structure: {
            liquidity: 'Cash on hand of $1.2B provides flexibility.',
            shareholder_returns: ['Ongoing buyback authorization'],
          },
          notable_footnotes: [
            { item: 'Note 7: Revenue recognition change', impact: 'Adjusts timing of subscription revenue.' },
          ],
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // Tabs should appear when content is present
    expect(screen.getByText('Guidance')).toBeInTheDocument()
    expect(screen.getByText('Liquidity')).toBeInTheDocument()
  })
})
