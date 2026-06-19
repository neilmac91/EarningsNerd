import React from 'react'
import { render, screen } from '@testing-library/react'
import { FullTextSearchResults } from '@/features/search/components/FullTextSearch'
import type { FullTextSearchHit } from '@/features/search/api/search-api'

const hit: FullTextSearchHit = {
  accession_no: '0000320193-24-000123',
  form: '10-K',
  filed_date: '2024-11-01',
  period_ending: '2024-09-28',
  cik: '320193',
  company: 'Apple Inc.',
  ticker: 'AAPL',
  document: 'aapl.htm',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl.htm',
}

describe('FullTextSearchResults', () => {
  it('renders a hit with company, ticker, form, dates and an external document link', () => {
    const { container } = render(<FullTextSearchResults hits={[hit]} />)
    expect(container.textContent).toContain('AAPL')
    expect(container.textContent).toContain('Apple Inc.')
    expect(container.textContent).toContain('10-K')
    expect(container.textContent).toContain('Filed 2024-11-01')
    expect(container.textContent).toContain('Period 2024-09-28')

    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe(hit.document_url)
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noreferrer')
  })

  it('falls back to sec_url when document_url is missing and labels an unknown filer', () => {
    const partial: FullTextSearchHit = { ...hit, company: null, ticker: null, document_url: null }
    const { container } = render(<FullTextSearchResults hits={[partial]} />)
    expect(container.textContent).toContain('Unknown filer')
    expect(screen.getByRole('link').getAttribute('href')).toBe(partial.sec_url)
  })

  it('renders a non-link row when no URL is available (no empty anchor)', () => {
    const noUrl: FullTextSearchHit = { ...hit, document_url: null, sec_url: null }
    const { container } = render(<FullTextSearchResults hits={[noUrl]} />)
    expect(screen.queryByRole('link')).toBeNull()
    expect(container.textContent).toContain('Apple Inc.')
  })

  it('renders one row per hit', () => {
    render(<FullTextSearchResults hits={[hit, { ...hit, accession_no: '0000320193-23-000077', document: 'aapl2.htm' }]} />)
    expect(screen.getAllByRole('link')).toHaveLength(2)
  })
})
