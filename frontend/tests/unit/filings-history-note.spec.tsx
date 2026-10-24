import React from 'react'
import { render, screen } from '@testing-library/react'

import FilingsHistoryNote from '@/features/filings/components/FilingsHistoryNote'
import { edgarCompanyUrl } from '@/features/companies/lib/edgar'

// P0-5 guardrail (data-quality plan): the filings panel must state the earliest date shown and
// link the company's full history on SEC.gov (its EDGAR list) by CIK.
describe('FilingsHistoryNote', () => {
  it('renders the since-date and a CIK-scoped external EDGAR link', () => {
    const { container } = render(
      <FilingsHistoryNote oldestFilingDate="2025-08-05T00:00:00+00:00" cik="0000019617" />,
    )
    expect(container.textContent).toContain('Showing filings since Aug 5, 2025')

    // A link to the source names SEC.gov, not EDGAR (D-058; evidenceVocabulary.spec.ts).
    const link = screen.getByRole('link', { name: /full history on sec\.gov/i })
    const href = link.getAttribute('href') ?? ''
    expect(href).toContain('https://www.sec.gov/cgi-bin/browse-edgar')
    expect(href).toContain('action=getcompany')
    expect(href).toContain('CIK=0000019617')
    // Every form, not only 10-Ks (CO-27): "full history" is the company's whole EDGAR list, the same company
    // link the lead uses, so EDGAR's own defaults replace the old type, owner and count filters.
    expect(href).not.toContain('type=')
    expect(href).toBe(edgarCompanyUrl('0000019617'))
    // The quiet source link's recipe (CO-28): underlined, with the brand focus ring; the icon is decorative.
    expect(link.className).toContain('focus-visible:shadow-ring-brand')
    expect(link.className).toContain('underline')
    expect(link.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
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
