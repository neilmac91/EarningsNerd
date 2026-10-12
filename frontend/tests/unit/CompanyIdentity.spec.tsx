import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { CompanyIdentity } from '@/features/companies/components/CompanyIdentity'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const COMPANY: Company = {
  id: 1,
  cik: '320193',
  ticker: 'AAPL',
  name: 'APPLE INC.',
  exchange: 'NASDAQ',
  stock_quote: { price: 227.52, change_percent: 1.2 },
}
const LATEST: Filing = {
  id: 3,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  report_date: '2025-09-27T00:00:00+00:00',
  accession_number: '0000320193-25-000079',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
}

/** The data-face line that holds `text`, with its middots dropped and its sr-only commas kept. */
const lineWith = (text: string) => screen.getByText(text, { exact: false }).closest('p') as HTMLElement

describe('CompanyIdentity', () => {
  it('states the company once: a breadcrumb, the h1 and its ticker in the data face', () => {
    render(<CompanyIdentity company={COMPANY} latest={LATEST} />)
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(crumbs).getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/')
    expect(within(crumbs).getByText('Apple Inc.')).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
    expect(screen.getByText('AAPL').className).toContain('font-data')
  })

  it('lists the facts the API returns, with the CIK as EDGAR prints it and a link to the company there', () => {
    render(<CompanyIdentity company={COMPANY} latest={null} />)
    const facts = lineWith('CIK 0000320193')
    expect(facts.className).toContain('font-data')
    expect(facts).toHaveTextContent(/NASDAQ\s*·\s*,\s*\$227\.52\s*\+1\.20%\s*·\s*,\s*CIK 0000320193/)
    const edgar = within(facts).getByRole('link', { name: 'Company on SEC EDGAR' })
    expect(edgar).toHaveAttribute('href', 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=320193')
    expect(edgar).toHaveAttribute('target', '_blank')
    expect(edgar).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('names the latest filing by form, period of report and filed date', () => {
    render(<CompanyIdentity company={COMPANY} latest={LATEST} />)
    const line = lineWith('Latest filing')
    expect(line).toHaveTextContent(/Latest filing 10-K\s*·\s*,\s*fiscal year ended Sep 27, 2025\s*·\s*,\s*filed Oct 31, 2025$/)
    // The form is weight in the ink, never a Badge.
    expect(within(line).getByText('10-K').className).toMatch(/font-semibold/)
    expect(within(line).queryByText('summary ready')).toBeNull()
  })

  it('says "summary ready" only when the latest filing has one', () => {
    render(<CompanyIdentity company={COMPANY} latest={LATEST} summaryReady />)
    expect(lineWith('Latest filing')).toHaveTextContent(/filed Oct 31, 2025\s*·\s*,\s*summary ready$/)
  })

  it('drops what it does not have: no quote, no exchange, no latest filing, no actions', () => {
    const { container } = render(<CompanyIdentity company={{ id: 2, cik: '1045810', ticker: 'NVDA', name: 'NVIDIA CORP' }} latest={null} />)
    expect(lineWith('CIK 0001045810')).toHaveTextContent(/^CIK 0001045810\s*·\s*,\s*Company on SEC EDGAR$/)
    expect(screen.queryByText('Latest filing', { exact: false })).toBeNull()
    expect(container.querySelector('button')).toBeNull()
  })

  it('renders the page’s actions beside the facts', () => {
    render(<CompanyIdentity company={COMPANY} latest={LATEST} actions={<button type="button">Open latest summary</button>} />)
    expect(screen.getByRole('button', { name: 'Open latest summary' })).toBeInTheDocument()
  })
})
