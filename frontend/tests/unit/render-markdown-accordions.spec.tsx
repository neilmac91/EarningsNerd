import React from 'react'
import { render, screen } from '@testing-library/react'
import SummarySections from '@/components/SummarySections'

describe('SummarySections renderMarkdownValue gating', () => {
  it('hides tabs when renderMarkdownValue yields blank/placeholder strings', () => {
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

    // Executive Summary always visible (shows unavailable sections)
    expect(screen.getByRole('button', { name: /executive summary/i })).toBeInTheDocument()

    // Tabs with empty/null content should be hidden
    expect(screen.queryByRole('button', { name: /^guidance$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^liquidity$/i })).not.toBeInTheDocument()

    // Unavailable sections disclosure should be shown
    expect(screen.getByText('Not included in this filing:')).toBeInTheDocument()
  })

  it('shows tabs when renderMarkdownValue returns real content', () => {
    const summary = {
      business_overview: 'Comprehensive overview of company performance and strategic initiatives.',
      raw_summary: {
        sections: {
          executive_snapshot: 'Comprehensive overview of company performance and strategic initiatives.',
          guidance_outlook: {
            guidance: 'Management reiterated full-year outlook with revenue expected to grow 12-15%.',
            drivers: ['Demand recovery in core markets'],
          },
          liquidity_capital_structure: {
            liquidity: 'Cash on hand of $1.2B provides flexibility for M&A and shareholder returns.',
            shareholder_returns: ['Ongoing buyback authorization of $500M'],
          },
          notable_footnotes: [
            { item: 'Note 7: Revenue recognition change', impact: 'Adjusts timing of subscription revenue.' },
          ],
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // Tabs should appear when content is present
    expect(screen.getByRole('button', { name: /^guidance$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^liquidity$/i })).toBeInTheDocument()
  })

  it('filters out placeholder content patterns from tab visibility', () => {
    const summary = {
      business_overview: 'Valid real content for the executive summary section.',
      raw_summary: {
        sections: {
          executive_snapshot: 'Valid real content for the executive summary section.',
          guidance_outlook: {
            outlook: 'Guidance requires full AI processing. Please retry for detailed analysis.',
          },
          liquidity_capital_structure: {
            summary: 'Not available in this partial summary. Retry for complete analysis.',
          },
          management_discussion_insights: {
            themes: ['Analysis is being processed. Preliminary data only.'],
          },
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // Executive Summary should be visible
    expect(screen.getByRole('button', { name: /executive summary/i })).toBeInTheDocument()

    // Tabs with placeholder patterns should be hidden
    expect(screen.queryByRole('button', { name: /^guidance$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^liquidity$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /md&a/i })).not.toBeInTheDocument()
  })
})
