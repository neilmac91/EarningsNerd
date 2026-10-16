import React from 'react'
import { render, screen } from '@testing-library/react'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'

describe('Financial metric Trace-to-Source', () => {
  it('shows a verified SEC XBRL label with the concept', () => {
    render(<MetricSourceLink url="https://sec.gov/x.htm" verified concept="Revenue" />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe('https://sec.gov/x.htm')
    expect(link.textContent).toContain('Revenue')
    expect(link.textContent).toContain('SEC XBRL')
    expect(link.getAttribute('aria-label')).toMatch(/SEC XBRL/i)
  })

  it('shows the honest "Cited" chip when unverified, never named "Source: Source"', () => {
    render(<MetricSourceLink url="https://sec.gov/x.htm" verified={false} />)
    const link = screen.getByRole('link', { name: 'Source: Cited' })
    expect(link.textContent).toContain('Cited')
    expect(link.textContent).not.toContain('SEC XBRL')
    expect(screen.queryByRole('link', { name: 'Source: Source' })).toBeNull()
  })

  it('renders nothing without a url', () => {
    const { container } = render(<MetricSourceLink url={null} verified />)
    expect(container.querySelector('a')).toBeNull()
  })
})
