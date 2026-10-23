import React from 'react'
import { render, screen } from '@testing-library/react'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'

describe('Financial metric Trace-to-Source', () => {
  it('shows "Matches filing" for a verified figure, with no concept prefix and no acronym', () => {
    render(<MetricSourceLink url="https://sec.gov/x.htm" verified />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe('https://sec.gov/x.htm')
    expect(link.textContent).toBe('Matches filing')
    expect(link.getAttribute('aria-label')).toBe('Source: Matches filing (opens in a new tab)')
  })

  it('shows the honest "Linked, not checked" chip when unverified, never named "Source: Source"', () => {
    render(<MetricSourceLink url="https://sec.gov/x.htm" verified={false} />)
    const link = screen.getByRole('link', { name: 'Source: Linked, not checked (opens in a new tab)' })
    expect(link.textContent).toContain('Linked, not checked')
    expect(link.textContent).not.toContain('Matches filing')
    expect(screen.queryByRole('link', { name: 'Source: Source' })).toBeNull()
  })

  it('renders nothing without a url', () => {
    const { container } = render(<MetricSourceLink url={null} verified />)
    expect(container.querySelector('a')).toBeNull()
  })
})
