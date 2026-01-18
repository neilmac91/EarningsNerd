import React from 'react'
import { render, screen } from '@testing-library/react'
import SummarySections from '@/components/SummarySections'

describe('SummarySections renderMarkdownValue gating', () => {
  it('hides additional accordions when renderMarkdownValue yields blank strings', () => {
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

    // Tabs should not appear when content is empty
    expect(screen.queryByText('Guidance & Drivers')).not.toBeInTheDocument()
    expect(screen.queryByText('Liquidity & Covenants')).not.toBeInTheDocument()
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
    expect(screen.getByText('Guidance & Drivers')).toBeInTheDocument()
    expect(screen.getByText('Liquidity & Covenants')).toBeInTheDocument()
  })
})
