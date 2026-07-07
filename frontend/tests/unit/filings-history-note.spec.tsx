import React from 'react'
import { render, screen } from '@testing-library/react'

import FilingsHistoryNote from '@/features/filings/components/FilingsHistoryNote'

// P0-5 guardrail (data-quality plan): the filings panel must state the earliest date shown and
// link the company's full history on SEC EDGAR by CIK.
describe('FilingsHistoryNote', () => {
  it('renders the since-date and a CIK-scoped external EDGAR link', () => {
    const { container } = render(
      <FilingsHistoryNote oldestFilingDate="2025-08-05" cik="0000019617" />,
    )
    expect(container.textContent).toContain('Showing filings since Aug 5, 2025')

    const link = screen.getByRole('link', { name: /full history on sec edgar/i })
    const href = link.getAttribute('href') ?? ''
    expect(href).toContain('https://www.sec.gov/cgi-bin/browse-edgar')
    expect(href).toContain('action=getcompany')
    expect(href).toContain('CIK=0000019617')
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('renders nothing without an oldest date or a CIK', () => {
    const a = render(<FilingsHistoryNote oldestFilingDate={null} cik="0000019617" />)
    expect(a.container.textContent).toBe('')
    const b = render(<FilingsHistoryNote oldestFilingDate="2025-08-05" cik={undefined} />)
    expect(b.container.textContent).toBe('')
  })
})
