import React from 'react'
import { render, screen } from '@testing-library/react'
import SummarySections from '@/components/SummarySections'

describe('SummarySections additional accordions', () => {
  it('hides tabs with placeholder/empty content and shows unavailable sections disclosure', () => {
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

    // Executive Summary tab should ALWAYS be visible (to show unavailable sections)
    expect(screen.getByRole('button', { name: /executive summary/i })).toBeInTheDocument()

    // Other tabs should be HIDDEN when content is empty/placeholder
    expect(screen.queryByRole('button', { name: /^guidance$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^liquidity$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^financials$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^risks$/i })).not.toBeInTheDocument()

    // Unavailable sections should be listed in the disclosure
    expect(screen.getByText('Not included in this filing:')).toBeInTheDocument()
    expect(screen.getByText(/Guidance data was not available/i)).toBeInTheDocument()
    expect(screen.getByText(/Liquidity data was not available/i)).toBeInTheDocument()
  })

  it('hides tabs with placeholder text like "Not available" or "requires full"', () => {
    const summary = {
      business_overview: 'Valid executive summary content here with real information.',
      raw_summary: {
        sections: {
          executive_snapshot: 'Valid executive summary content here with real information.',
          financial_highlights: {
            notes: 'Not available - retry for full analysis',
          },
          risk_factors: [
            {
              summary: 'Risk factors are available in the full SEC filing.',
              supporting_evidence: 'Retry generation for AI-powered risk analysis.',
            }
          ],
          management_discussion_insights: {
            themes: ['MD&A requires full AI processing. Please retry.']
          },
          guidance_outlook: {
            outlook: 'Guidance requires full AI processing.'
          },
          liquidity_capital_structure: {
            summary: 'Liquidity analysis requires full AI processing.'
          },
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // Executive Summary should be visible with valid content
    expect(screen.getByRole('button', { name: /executive summary/i })).toBeInTheDocument()

    // Other tabs with placeholder content should be hidden
    expect(screen.queryByRole('button', { name: /^guidance$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^liquidity$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^financials$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^risks$/i })).not.toBeInTheDocument()
  })

  it('shows tabs when they have real substantive content', () => {
    const summary = {
      business_overview: 'This is a comprehensive executive summary with detailed analysis of the company performance.',
      raw_summary: {
        sections: {
          executive_snapshot: 'Comprehensive analysis of Q3 2025 performance showing strong growth.',
          financial_highlights: {
            notes: 'Revenue grew 15% year-over-year driven by strong product sales.',
          },
          risk_factors: [
            {
              summary: 'Supply chain disruptions may impact production capacity.',
              supporting_evidence: 'Management noted ongoing semiconductor shortages in earnings call.',
            }
          ],
          management_discussion_insights: {
            themes: ['Strong operating leverage drove margin expansion of 200bps.']
          },
          guidance_outlook: {
            outlook: 'Management raised full-year guidance citing strong demand.'
          },
          liquidity_capital_structure: {
            summary: 'Cash position of $2.5B provides ample flexibility for strategic investments.'
          },
        },
      },
    }

    render(<SummarySections summary={summary as any} metrics={[]} />)

    // All tabs should be visible when they have real content
    expect(screen.getByRole('button', { name: /executive summary/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^financials$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^risks$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /md&a/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^guidance$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^liquidity$/i })).toBeInTheDocument()
  })
})
