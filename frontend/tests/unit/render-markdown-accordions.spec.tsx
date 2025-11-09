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

    expect(screen.queryByText('Additional Information')).not.toBeInTheDocument()
    expect(screen.queryByText('Forward Outlook & Guidance')).not.toBeInTheDocument()
    expect(screen.queryByText('Liquidity & Capital Structure')).not.toBeInTheDocument()
    expect(screen.queryByText('Notable Footnotes')).not.toBeInTheDocument()
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

    expect(screen.getByText('Additional Information')).toBeInTheDocument()
    expect(screen.getByText('Forward Outlook & Guidance')).toBeInTheDocument()
    expect(screen.getByText('Liquidity & Capital Structure')).toBeInTheDocument()
    expect(screen.getByText('Notable Footnotes')).toBeInTheDocument()
  })
})
