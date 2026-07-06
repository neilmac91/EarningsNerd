import React from 'react'
import { render, screen } from '@testing-library/react'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'
import { SummaryFinancials } from '@/features/summaries/components/SummaryFinancials'
import type { MetricItem } from '@/types/summary'

describe('Financial metric Trace-to-Source', () => {
  it('shows a verified SEC XBRL label with the concept', () => {
    render(<MetricSourceLink url="https://sec.gov/x.htm" verified concept="Revenue" />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe('https://sec.gov/x.htm')
    expect(link.textContent).toContain('Revenue')
    expect(link.textContent).toContain('SEC XBRL')
    expect(link.getAttribute('aria-label')).toMatch(/SEC XBRL/i)
  })

  it('shows a plain source link when unverified', () => {
    render(<MetricSourceLink url="https://sec.gov/x.htm" verified={false} />)
    const link = screen.getByRole('link')
    expect(link.textContent).toContain('Source')
    expect(link.textContent).not.toContain('SEC XBRL')
  })

  it('renders nothing without a url', () => {
    const { container } = render(<MetricSourceLink url={null} verified />)
    expect(container.querySelector('a')).toBeNull()
  })

  it('SummaryFinancials renders a per-metric verified source link', () => {
    const metrics: MetricItem[] = [
      {
        metric: 'Total Revenue',
        current_period: '$391.0B',
        prior_period: '$383.3B',
        source_url: 'https://www.sec.gov/x.htm',
        source_verified: true,
        xbrl_concept: 'Revenue',
      },
    ]
    render(<SummaryFinancials metrics={metrics} />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe('https://www.sec.gov/x.htm')
    expect(link.textContent).toContain('SEC XBRL')
  })

  it('SummaryFinancials omits the link for un-enriched metrics (backward compatible)', () => {
    const metrics: MetricItem[] = [
      { metric: 'Backlog', current_period: '$10B', prior_period: '$9B' },
    ]
    render(<SummaryFinancials metrics={metrics} />)
    expect(screen.queryByRole('link')).toBeNull()
  })
})
